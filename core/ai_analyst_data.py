"""
AI 多智能体分析 — 数据层
封装通达信(mootdx)数据获取，为 LLM Agent 提供工具函数

关键设计：
- 线程锁保护 mootdx TCP 单例，防止并发崩溃
- StockDataFrame.retype() 而非 wrap()，避免 "date" 列名解析冲突
- stockstats 懒加载：先触发 stock[indicator] 再按行迭代
"""

import threading
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np
from mootdx.quotes import Quotes

# --- 通达信客户端单例 + 线程锁 ---
_tdx_client: Optional[Quotes] = None
_tdx_lock = threading.Lock()


def _get_client() -> Quotes:
    global _tdx_client
    if _tdx_client is None:
        _tdx_client = Quotes.factory(market="std")
    return _tdx_client


def _normalize_symbol(symbol: str) -> str:
    """去掉交易所后缀，如 '600519.SS' -> '600519'"""
    return symbol.split(".")[0] if "." in symbol else symbol


def _fix_datetime_ambiguity(df: pd.DataFrame) -> pd.DataFrame:
    """修复 mootdx 返回的 DataFrame 中 datetime 既是 index 又是 column 的歧义。"""
    # 吃掉 index 与 columns 之间的重复列
    try:
        dup_cols = set(df.index.names or []) & set(df.columns)
        for col in dup_cols:
            if col and col != '':
                df = df.drop(columns=[col])
    except Exception:
        pass

    # 如果 datetime 在 index 中但不在 columns 中，reset_index 恢复它
    df_index_name = df.index.name or ''
    if 'datetime' in df_index_name.lower() or any('datetime' in (n or '').lower() for n in (df.index.names or [])):
        df = df.reset_index()

    # 确保有 datetime 列并排序
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors='coerce')
        df = df.sort_values("datetime")
    return df


# ============================================================
#  工具函数（供 LLM Agent function-calling 使用）
# ============================================================

def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """获取股票 K 线数据，返回格式化的 CSV 文本。

    Args:
        symbol: 股票代码，如 '600519.SS' 或 '600519'
        start_date: 起始日期 'YYYY-mm-dd'
        end_date: 结束日期 'YYYY-mm-dd'
    """
    code = _normalize_symbol(symbol)
    client = _get_client()

    # 估算需要拉取的天数
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days + 30  # 加 buffer 覆盖非交易日
    except Exception:
        days = 365

    offset = min(max(days, 60), 800)

    with _tdx_lock:
        bars = client.bars(symbol=code, category=4, offset=offset)

    if bars is None or bars.empty:
        return f"NO_DATA: 无法获取 {symbol} 的 K 线数据"

    df = _fix_datetime_ambiguity(bars.copy())

    # 按日期范围过滤
    try:
        df = df[(df["datetime"] >= start_dt) & (df["datetime"] <= end_dt)]
    except Exception:
        pass

    if df.empty:
        return f"NO_DATA: {symbol} 在 {start_date}~{end_date} 无数据"

    # 格式化输出
    lines = [
        f"# Stock data for {symbol} ({code}) from {start_date} to {end_date}",
        f"# Total records: {len(df)}",
        f"# Source: 通达信 (mootdx TCP)",
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Date,Open,High,Low,Close,Volume,amount",
    ]
    for _, row in df.iterrows():
        dt = row.get("datetime")
        if isinstance(dt, pd.Timestamp):
            dt = dt.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(
            f"{dt},{row.get('open','')},{row.get('high','')},"
            f"{row.get('low','')},{row.get('close','')},"
            f"{row.get('vol','')},{row.get('amount','')}"
        )
    return "\n".join(lines)


def get_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 60,
) -> str:
    """获取单个技术指标的历史值。

    Args:
        symbol: 股票代码
        indicator: 指标名称，支持: close_10_ema, close_50_sma, close_200_sma,
                   macd, macds, macdh, rsi, boll, boll_ub, boll_lb, atr, vwma
        curr_date: 分析日期 'YYYY-mm-dd'
        look_back_days: 回看天数

    Returns:
        格式化的指标数据文本
    """
    from stockstats import StockDataFrame

    code = _normalize_symbol(symbol)
    client = _get_client()

    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    except Exception:
        return f"ERROR: 无效日期格式 {curr_date}"

    # 获取足够长的 K 线数据（指标计算需要前置数据）
    offset = look_back_days + 150

    with _tdx_lock:
        bars = client.bars(symbol=code, category=4, offset=offset)

    if bars is None or bars.empty:
        return f"NO_DATA: 无法获取 {symbol} 的 K 线数据用于指标计算"

    df = _fix_datetime_ambiguity(bars.copy())

    # 保存日期列
    if "datetime" in df.columns:
        dates = pd.to_datetime(df["datetime"])
    else:
        return "ERROR: 数据缺少 datetime 列"

    # 只保留 stockstats 需要的 OHLCV 列
    df = df[["open", "close", "high", "low", "vol"]].copy()
    df = df.rename(columns={"vol": "volume"})

    # 用 StockDataFrame.retype() 计算指标（不会解析列名作为表达式）
    try:
        stock = StockDataFrame.retype(df)
    except Exception as e:
        return f"ERROR: stockstats retype() 失败: {e}"

    # 将日期重新附加
    stock["date"] = dates.dt.strftime("%Y-%m-%d").values

    # 触发 stockstats 懒加载计算
    try:
        _ = stock[indicator]
    except (KeyError, ValueError) as e:
        return f"ERROR: 无法计算指标 '{indicator}': {e}"

    # 按日期范围输出
    before_dt = curr_dt - timedelta(days=look_back_days)
    lines = [f"# {indicator} for {symbol} from {before_dt.strftime('%Y-%m-%d')} to {curr_date}"]

    for _, row in stock.iterrows():
        date_str = str(row.get("date", ""))
        try:
            val = row[indicator]
            if isinstance(val, (float, np.floating)) and np.isnan(val):
                lines.append(f"{date_str}: N/A: Not a trading day")
            else:
                lines.append(f"{date_str}: {val}")
        except (KeyError, ValueError):
            lines.append(f"{date_str}: N/A: Not a trading day")

    lines.append("# Source: 通达信 (mootdx) + stockstats")
    return "\n".join(lines)


def get_verified_snapshot(
    symbol: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """获取经验证的 OHLCV + 全部技术指标快照，用于交叉验证。

    Args:
        symbol: 股票代码
        curr_date: 分析日期 'YYYY-mm-dd'
        look_back_days: 回看天数（用于最近收盘价表格）
    """
    code = _normalize_symbol(symbol)
    client = _get_client()
    indicators = [
        "close_10_ema", "close_50_sma", "close_200_sma",
        "rsi", "boll", "boll_ub", "boll_lb",
        "macd", "macds", "macdh", "atr",
    ]

    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    except Exception:
        return f"ERROR: 无效日期格式 {curr_date}"

    # 获取足够数据
    offset = look_back_days + 200

    with _tdx_lock:
        bars = client.bars(symbol=code, category=4, offset=offset)

    if bars is None or bars.empty:
        return f"NO_DATA: 无法获取 {symbol} 的 K 线数据"

    df = _fix_datetime_ambiguity(bars.copy())
    if "datetime" in df.columns:
        dates = pd.to_datetime(df["datetime"])
        date_strs = dates.dt.strftime("%Y-%m-%d")
    else:
        return "ERROR: 数据缺少 datetime 列"

    # 只保留 curr_date 及之前的数据（用普通 DataFrame 过滤）
    mask = date_strs <= curr_date
    df = df[mask].copy()
    date_strs = date_strs[mask]
    if df.empty:
        return f"NO_DATA: {symbol} 在 {curr_date} 之前无数据"

    df_ohlcv = df[["open", "close", "high", "low", "vol"]].copy()
    df_ohlcv = df_ohlcv.rename(columns={"vol": "volume"})

    from stockstats import StockDataFrame

    try:
        stock = StockDataFrame.retype(df_ohlcv)
    except Exception as e:
        return f"ERROR: stockstats retype() 失败: {e}"

    # ⚠️ stockstats 只用于指标计算，不要通过 stock.iloc/stock["date"] 访问数据
    latest_idx = len(df_ohlcv) - 1
    latest_date = date_strs.iloc[-1]
    latest_open = df_ohlcv["open"].iloc[-1]
    latest_high = df_ohlcv["high"].iloc[-1]
    latest_low = df_ohlcv["low"].iloc[-1]
    latest_close = df_ohlcv["close"].iloc[-1]
    latest_vol = df_ohlcv["volume"].iloc[-1]

    # 构建验证快照
    lines = [
        f"## Verified market data snapshot for {symbol}",
        f"- Requested analysis date: {curr_date}",
        f"- Latest trading row used: {latest_date}",
        f"- Rows after the requested analysis date are excluded before verification.",
        "",
        "### Latest verified OHLCV row",
        "| Field | Value |",
        "|---|---:|",
        f"| Open | {latest_open} |",
        f"| High | {latest_high} |",
        f"| Low | {latest_low} |",
        f"| Close | {latest_close} |",
        f"| Volume | {latest_vol} |",
        "",
        "### Verified technical indicators (latest row)",
        "| Indicator | Value |",
        "|---|---:|",
    ]

    for ind in indicators:
        try:
            val = stock[ind].dropna()
            if len(val) > 0:
                lines.append(f"| {ind} | {float(val.iloc[-1]):.2f} |")
            else:
                lines.append(f"| {ind} | N/A |")
        except Exception:
            lines.append(f"| {ind} | N/A |")

    # 最近收盘价表格
    lines.append("")
    lines.append("### Recent verified closes (last 30 rows)")
    lines.append("| Date | Close |")
    lines.append("|---|---:|")
    n_recent = min(30, len(df_ohlcv))
    for i in range(len(df_ohlcv) - n_recent, len(df_ohlcv)):
        lines.append(f"| {date_strs.iloc[i]} | {df_ohlcv['close'].iloc[i]} |")

    lines.append("")
    lines.append(
        "Use this snapshot as the source of truth for exact OHLCV, price-level, "
        "and indicator-value claims."
    )
    return "\n".join(lines)


def get_fundamentals(symbol: str) -> str:
    """获取股票基本面信息（通过通达信 finance 接口 + 东方财富 PE/PB/市值）。

    Args:
        symbol: 股票代码
    """
    code = _normalize_symbol(symbol)
    client = _get_client()

    lines = [
        f"# 基本面数据: {symbol} ({code})",
    ]

    # ---- 1. 东方财富 PE/PB/市值（更可靠）----
    try:
        import requests as _req
        url = "https://push2his.eastmoney.com/api/qt/clist/get"
        market_code = "1" if code.startswith(("6", "9")) else "0"
        fs_val = f"m:{market_code}+t:2,m:{market_code}+t:23" if code.startswith("6") else f"m:0+t:6,m:0+t:80"
        params = {
            "pn": "1", "pz": "100",
            "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f12",
            "fs": fs_val,
            "fields": "f9,f12,f20,f23,f115",
        }
        r = _req.get(url, params=params, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
        }, timeout=10)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
        for item in items:
            if str(item.get("f12", "")) == code:
                pe = item.get("f9")
                pb = item.get("f23")
                total_mv = item.get("f20")
                lines.append(f"# 来源: 东方财富 (实时估值数据)")
                if pe is not None and float(pe) != 0:
                    lines.append(f"PE(市盈率): {pe}")
                else:
                    lines.append(f"PE(市盈率): 数据不可用")
                if pb is not None and float(pb) != 0:
                    lines.append(f"PB(市净率): {pb}")
                if total_mv is not None and float(total_mv) != 0:
                    mv_yi = float(total_mv) / 1e8
                    lines.append(f"总市值: {mv_yi:.1f}亿")
                break
    except Exception:
        pass

    # ---- 2. 通达信 finance 接口（补充数据）----
    with _tdx_lock:
        try:
            finance = client.finance(symbol=code)
        except Exception as e:
            lines.append(f"# 通达信 finance 接口调用失败: {e}")
            return "\n".join(lines)

    if finance is None or (isinstance(finance, pd.DataFrame) and finance.empty):
        lines.append(f"# 通达信未返回额外数据")
    elif isinstance(finance, pd.DataFrame):
        lines.append(f"# 来源: 通达信 finance (公司基本信息)")
        for col in finance.columns:
            val = finance[col].iloc[0] if len(finance) > 0 else "N/A"
            lines.append(f"{col}: {val}")
    else:
        lines.append(str(finance))

    return "\n".join(lines)


def get_market_data(
    symbol: str,
    curr_date: str,
    look_back_days: int = 90,
) -> str:
    """联合获取 K线 + 全部核心指标，一次调用替代多次工具调用。

    大幅减少 LLM tool-calling 回合数（从 8-10 次降到 1 次），
    将第一阶段耗时从 80-100s 降到 ~10s。
    """
    code = _normalize_symbol(symbol)
    client = _get_client()
    indicators = [
        "close_10_ema", "close_50_sma", "close_200_sma",
        "rsi", "boll", "boll_ub", "boll_lb",
        "macd", "macds", "macdh", "atr",
    ]

    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    except Exception:
        return f"ERROR: 无效日期格式 {curr_date}"

    offset = look_back_days + 250

    with _tdx_lock:
        bars = client.bars(symbol=code, category=4, offset=offset)

    if bars is None or bars.empty:
        return f"NO_DATA: 无法获取 {symbol} 的K线数据"

    df = _fix_datetime_ambiguity(bars.copy())
    if "datetime" in df.columns:
        dates = pd.to_datetime(df["datetime"])
    else:
        return "ERROR: 数据缺少 datetime 列"

    # 过滤到 curr_date 及之前
    mask = dates.dt.strftime("%Y-%m-%d") <= curr_date
    df = df[mask].copy()
    dates = dates[mask]

    df_ohlcv = df[["open", "close", "high", "low", "vol"]].copy()
    df_ohlcv = df_ohlcv.rename(columns={"vol": "volume"})

    from stockstats import StockDataFrame

    try:
        stock = StockDataFrame.retype(df_ohlcv)
    except Exception as e:
        return f"ERROR: stockstats retype() 失败: {e}"

    # 只输出最近 look_back_days 条 — 精简以加速 LLM 处理
    n_show = min(look_back_days, len(df))
    start_idx = len(df) - n_show

    latest_idx = len(df) - 1
    lines = [
        f"# 联合行情数据: {symbol}({code})",
        f"# 分析日期: {curr_date} | 最近 {n_show} 条K线 | 最新交易日: {dates.iloc[latest_idx].strftime('%Y-%m-%d')}",
        "",
        "## 最新 OHLCV + 指标快照（最近 5 条）",
        "| Date | Open | High | Low | Close | Vol | " + " | ".join(indicators) + " |",
        "|" + "|---:|" * (len(indicators) + 6),
    ]

    last_n_start = max(start_idx, len(df) - 5)
    for i in range(last_n_start, len(df)):
        row_parts = [
            dates.iloc[i].strftime("%Y-%m-%d"),
            f"{df_ohlcv['open'].iloc[i]:.2f}",
            f"{df_ohlcv['high'].iloc[i]:.2f}",
            f"{df_ohlcv['low'].iloc[i]:.2f}",
            f"{df_ohlcv['close'].iloc[i]:.2f}",
            str(int(df_ohlcv['volume'].iloc[i])),
        ]
        for ind in indicators:
            try:
                val = stock[ind].iloc[i]
                row_parts.append(f"{val:.2f}" if not pd.isna(val) else "N/A")
            except Exception:
                row_parts.append("N/A")
        lines.append("| " + " | ".join(row_parts) + " |")

    # 周度摘要（每5条取1条，加速趋势判断）
    lines.append("")
    lines.append("## 周度 OHLCV 摘要（每5个交易日）")
    lines.append("| Date | Close |")
    lines.append("|---:|---:|")
    for i in range(start_idx, len(df), 5):
        lines.append(f"| {dates.iloc[i].strftime('%Y-%m-%d')} | {df_ohlcv['close'].iloc[i]:.2f} |")
    # Ensure latest is included
    if (len(df) - 1 - start_idx) % 5 != 1 and len(df) > start_idx + 1:
        lines.append(f"| {dates.iloc[latest_idx].strftime('%Y-%m-%d')} | {df_ohlcv['close'].iloc[latest_idx]:.2f} |")

    return "\n".join(lines)


# ============================================================
#  批量获取辅助函数
# ============================================================

def get_symbol_name(code: str) -> str:
    """获取股票名称，带缓存"""
    try:
        from core.stock_utils import get_name_batch
        names = get_name_batch([code])
        return names.get(code, code) if names else code
    except Exception:
        return code
