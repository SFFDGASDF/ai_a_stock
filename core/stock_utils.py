"""
A股短线策略 V3 公共工具模块
提供: 股票列表、大盘检测、换手率、资金流向、技术指标、量价背离、RPS、ATR等
"""
import logging
logging.getLogger("tdxpy").setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import pandas as pd
import numpy as np
import requests
import time
import sys

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}

_client = None

def get_client():
    global _client
    if _client is None:
        _client = Quotes.factory(market="std")
    return _client


# ============================================================
#  1. 股票列表
# ============================================================

def get_stock_list():
    """获取沪深A股列表（排除ST/N/C/301/688），带重试容错"""
    c = get_client()

    sh = _safe_stocks(c, market=1)
    sz = _safe_stocks(c, market=0)

    if sh is None and sz is None:
        raise ConnectionError("通达信连接失败，请确认 mootdx 服务可用（通常需要打开通达信客户端或配置行情服务器）")

    dfs = []
    if sh is not None:
        dfs.append(sh)
    if sz is not None:
        dfs.append(sz)
    df_all = pd.concat(dfs, ignore_index=True)

    codes = []
    for _, s in df_all.iterrows():
        code = str(s.get("code", ""))
        name = str(s.get("name", ""))
        if (len(code) == 6
                and not name.startswith(("ST", "st", "*ST", "N", "C"))
                and code[:3] in ("600", "601", "603", "605", "000", "002", "003", "300")
                and code[:3] != "301"):
            codes.append((code, name))
    return codes


def _safe_stocks(client, market, retries=3):
    """安全获取股票列表，带重试"""
    import time as _time
    for attempt in range(retries):
        try:
            result = client.stocks(market=market)
            if result is not None and len(result) > 0:
                return result
        except Exception:
            pass
        if attempt < retries - 1:
            _time.sleep(1)
    return None


# ============================================================
#  2. 大盘环境检测
# ============================================================

def get_market_env(codes_list=None, sample_n=500):
    """返回 (env_label, market_score, up_ratio, down_ratio, index_status)
    market_score: 2=强势, 1=偏强, 0=震荡, -1=偏弱, -2=弱势
    """
    c = get_client()
    up_count = 0
    down_count = 0
    flat_count = 0
    total_count = 0

    # 三大指数
    indices = {"上证指数": "sh000001", "深证成指": "sz399001", "创业板指": "sz399006"}
    index_status = {}
    for idx_name, idx_code in indices.items():
        try:
            raw = idx_code[2:]
            q = c.quotes(symbol=[raw])
            if q is not None and len(q) > 0:
                row = q.iloc[0]
                price = float(row.get("price", 0) or 0)
                prev = float(row.get("last_close", 0) or 0)
                if price > 0 and prev > 0:
                    index_status[idx_name] = {"price": price, "chg": (price / prev - 1) * 100}
        except:
            pass

    # 涨跌家数
    if codes_list is None:
        codes_list = [c for c, _ in get_stock_list()]
    sample = codes_list[:sample_n]
    for i in range(0, len(sample), 80):
        batch = sample[i:i + 80]
        try:
            quotes = c.quotes(symbol=batch)
            if quotes is None or len(quotes) == 0:
                continue
            for _, q in quotes.iterrows():
                price = float(q.get("price", 0) or 0)
                prev = float(q.get("last_close", 0) or 0)
                if price <= 0 or prev <= 0:
                    continue
                total_count += 1
                chg = (price / prev - 1) * 100
                if chg > 0.5:
                    up_count += 1
                elif chg < -0.5:
                    down_count += 1
                else:
                    flat_count += 1
        except:
            pass
        time.sleep(0.05)

    up_ratio = up_count / total_count * 100 if total_count > 0 else 50
    down_ratio = down_count / total_count * 100 if total_count > 0 else 50

    if up_ratio >= 60:
        market_score = 2
        env_label = "强势（涨多跌少）"
    elif up_ratio >= 50:
        market_score = 1
        env_label = "偏强"
    elif up_ratio >= 40:
        market_score = 0
        env_label = "震荡"
    elif up_ratio >= 30:
        market_score = -1
        env_label = "偏弱"
    else:
        market_score = -2
        env_label = "弱势（跌多涨少）"

    return env_label, market_score, up_ratio, down_ratio, index_status


# ============================================================
#  3. 批量获取换手率+资金流向（东方财富 push2his）
# ============================================================

# 全市场数据缓存（每天缓存一次）
_extra_data_cache = {}
_extra_data_cache_date = None

def _safe_float(val):
    """安全转float，处理 '-' 和 None"""
    if val in ("-", "", None):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def _fetch_market_extra_data(market_id, fs_val, label):
    """拉取单个市场全部股票的换手率+大单净量+量比（多页）"""
    data = {}
    url = "https://push2his.eastmoney.com/api/qt/clist/get"
    for pn in range(1, 50):
        params = {
            "pn": str(pn), "pz": "100",
            "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f12",
            "fs": fs_val,
            "fields": "f8,f12,f62,f184",
        }
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            d = r.json()
            if d.get("data") is None:
                break
            items = d["data"].get("diff") or []
            if not items:
                break
            for item in items:
                code = str(item.get("f12", ""))
                data[code] = {
                    "turnover": _safe_float(item.get("f8")),
                    "main_net": _safe_float(item.get("f62")),
                    "volume_ratio": _safe_float(item.get("f184")),
                }
        except:
            break
        if pn % 5 == 0:
            print(f"      换手率 {label} 第{pn}页 ({len(data)}只)...")
            sys.stdout.flush()
        time.sleep(0.15)
    return data

def get_extra_data_batch(codes):
    """
    批量获取换手率 + 大单净量（带日缓存）
    codes: list of str, 如 ['000001', '600519']
    返回 dict: {code: {'turnover': float, 'main_net': float, 'volume_ratio': float}}
    """
    global _extra_data_cache, _extra_data_cache_date
    result = {}
    if not codes:
        return result

    codes_set = set(codes)
    today = time.strftime("%Y%m%d")

    # 如果缓存过期，重新拉全市场数据
    if _extra_data_cache_date != today or not _extra_data_cache:
        print("    (拉取全市场换手率+资金数据, 约30秒...)")
        sys.stdout.flush()
        all_data = {}
        for market_id, fs_val, label in [
            (0, "m:0+t:6,m:0+t:80", "深市"),
            (1, "m:1+t:2,m:1+t:23", "沪市"),
        ]:
            market_data = _fetch_market_extra_data(market_id, fs_val, label)
            all_data.update(market_data)
        _extra_data_cache = all_data
        _extra_data_cache_date = today

    # 从缓存中查找候选股票
    for code in codes:
        if code in _extra_data_cache:
            result[code] = _extra_data_cache[code]

    return result


# ============================================================
#  3b. 市场情绪数据（涨停/跌停/炸板率/连板高度）
# ============================================================

def get_limit_up_sentiment():
    """
    获取当日市场情绪指标
    返回 dict: {
        'limit_up_count': int,    # 涨停家数
        'limit_down_count': int,  # 跌停家数
        'broken_board_count': int, # 炸板家数
        'broken_rate': float,     # 炸板率 (0-100)
        'max_conn_board': int,    # 最高连板数
        'sentiment_score': float, # 市场温度 (0-100)
        'sentiment_label': str,   # 情绪标签
    }
    """
    result = {
        "limit_up_count": 0, "limit_down_count": 0,
        "broken_board_count": 0, "broken_rate": 0,
        "max_conn_board": 0, "sentiment_score": 50,
        "sentiment_label": "中性",
    }

    try:
        # 用 clist 获取涨停/跌停家数（从缓存数据中统计）
        # 同时拉取涨停板专题数据
        url = "https://push2his.eastmoney.com/api/qt/clist/get"
        
        # 涨停股池
        limit_up_codes = set()
        broken_codes = set()
        
        for pn in range(1, 10):
            params = {
                "pn": str(pn), "pz": "100",
                "po": "1", "np": "1",
                "fltt": "2", "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": "f2,f3,f12",
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            d = r.json()
            if d.get("data") is None:
                break
            items = d["data"].get("diff") or []
            if not items:
                break
            for item in items:
                chg = _safe_float(item.get("f3"))
                code = str(item.get("f12", ""))
                if chg >= 9.5:
                    limit_up_codes.add(code)
                elif chg <= -9.5:
                    result["limit_down_count"] += 1
            # 如果这一页最低涨幅都<9.5%，后面的更不会有涨停
            if items:
                last_chg = _safe_float(items[-1].get("f3"))
                if last_chg < 9.5:
                    break
            time.sleep(0.1)
        
        result["limit_up_count"] = len(limit_up_codes)
        
        # 炸板数据：从炸板股池获取
        for pn in range(1, 5):
            params2 = {
                "pn": str(pn), "pz": "100",
                "po": "1", "np": "1",
                "fltt": "2", "invt": "2",
                "fid": "f3",
                "fs": "b:DLZGJJ+tc:?",
                "fields": "f12,f14",
            }
            try:
                r2 = requests.get(url, params=params2, headers=HEADERS, timeout=10)
                d2 = r2.json()
                if d2.get("data") is None or not d2["data"].get("diff"):
                    break
                result["broken_board_count"] += len(d2["data"]["diff"])
            except:
                break
            time.sleep(0.1)
        
        # 计算炸板率
        total_board = result["limit_up_count"] + result["broken_board_count"]
        if total_board > 0:
            result["broken_rate"] = result["broken_board_count"] / total_board * 100
        
        # 计算市场温度 (0-100)
        # 温度 = f(涨跌比) * 0.4 + f(涨停数) * 0.3 + (100-炸板率) * 0.3
        if _extra_data_cache:
            up_count = sum(1 for code, data in _extra_data_cache.items() 
                          if code in limit_up_codes)
            # 涨跌比从market_env来，这里简化
            up_down_score = 50  # 默认50
        
        # 涨停温度
        lu_score = min(100, result["limit_up_count"] * 2)
        
        # 炸板温度（炸板率越低越好）
        broken_score = max(0, 100 - result["broken_rate"] * 2)
        
        result["sentiment_score"] = min(100, lu_score * 0.4 + broken_score * 0.3 + 50 * 0.3)
        
        # 情绪标签
        s = result["sentiment_score"]
        if s >= 75:
            result["sentiment_label"] = "🔥 火爆"
        elif s >= 60:
            result["sentiment_label"] = "☀ 偏暖"
        elif s >= 40:
            result["sentiment_label"] = "☁ 中性"
        elif s >= 25:
            result["sentiment_label"] = "❄ 偏冷"
        else:
            result["sentiment_label"] = "🧊 冰点"
        
    except Exception as e:
        pass
    
    return result


# ============================================================
#  3c. 基本面数据（PE/PB/市值）
# ============================================================

# 基本面缓存
_fundamental_cache = {}
_fundamental_cache_date = None

def _fetch_market_fundamental(market_id, fs_val):
    """拉取单市场PE/PB/市值（多页）"""
    data = {}
    url = "https://push2his.eastmoney.com/api/qt/clist/get"
    for pn in range(1, 50):
        params = {
            "pn": str(pn), "pz": "100",
            "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f12",
            "fs": fs_val,
            "fields": "f9,f12,f20,f23,f115",
        }
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            d = r.json()
            if d.get("data") is None:
                break
            items = d["data"].get("diff") or []
            if not items:
                break
            for item in items:
                code = str(item.get("f12", ""))
                data[code] = {
                    "pe": _safe_float(item.get("f9")),
                    "pb": _safe_float(item.get("f23")),
                    "total_mv": _safe_float(item.get("f20")),
                }
        except:
            break
        if pn % 5 == 0:
            print(f"      基本面 第{pn}页 ({len(data)}只)...")
            sys.stdout.flush()
        time.sleep(0.15)
    return data

def get_fundamental_data_batch(codes):
    """
    批量获取PE/PB/总市值（带日缓存）
    返回 dict: {code: {'pe': float, 'pb': float, 'total_mv': float}}
    """
    global _fundamental_cache, _fundamental_cache_date
    result = {}
    if not codes:
        return result
    
    today = time.strftime("%Y%m%d")
    if _fundamental_cache_date != today or not _fundamental_cache:
        all_data = {}
        for market_id, fs_val in [
            (0, "m:0+t:6,m:0+t:80"),
            (1, "m:1+t:2,m:1+t:23"),
        ]:
            market_data = _fetch_market_fundamental(market_id, fs_val)
            all_data.update(market_data)
        _fundamental_cache = all_data
        _fundamental_cache_date = today
    
    for code in codes:
        if code in _fundamental_cache:
            result[code] = _fundamental_cache[code]
    
    return result


# ============================================================
#  3d. 真实 RPS 计算（全市场排名）
# ============================================================

def calc_true_rps(code, chg_20d, chg_60d=None, global_returns_20=None, global_returns_60=None):
    """
    计算真实RPS（相对价格强度）
    基于全市场N日涨幅排名百分位
    
    如果 global_returns_* 已传入则直接使用，否则需要外部预先计算
    """
    rps20 = 50.0
    rps60 = 50.0
    
    if global_returns_20 and len(global_returns_20) > 10:
        # 计算chg_20d在global_returns_20中的分位
        rank = sum(1 for r in global_returns_20 if r <= chg_20d)
        rps20 = rank / len(global_returns_20) * 100
    
    if chg_60d is not None and global_returns_60 and len(global_returns_60) > 10:
        rank = sum(1 for r in global_returns_60 if r <= chg_60d)
        rps60 = rank / len(global_returns_60) * 100
    
    return rps20, rps60


# ============================================================
#  3e. 行业板块动量
# ============================================================

def get_industry_momentum(codes_with_chg=None, top_n=20):
    """
    计算行业板块动量排名
    通过东财行业板块指数涨跌幅排序
    
    如果提供 codes_with_chg: [(code, chg_5d), ...]
    返回 dict: {code: industry_rank_percentile}
    """
    result = {}
    
    # 获取行业板块涨跌幅排名
    try:
        url = "https://push2his.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100",
            "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f12,f14",
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
        
        industry_ranks = {}
        for rank, item in enumerate(items):
            ind_name = str(item.get("f14", ""))
            ind_chg = _safe_float(item.get("f3"))
            industry_ranks[ind_name] = {
                "rank": rank + 1,
                "total": len(items),
                "chg": ind_chg,
                "percentile": (1 - (rank + 1) / len(items)) * 100,
            }
        
        # 返回行业动量排名数据
        result = {
            "industry_list": industry_ranks,
            "total_industries": len(items),
            "top_industries": [k for k, v in sorted(
                industry_ranks.items(), 
                key=lambda x: x[1]["percentile"], 
                reverse=True
            )[:top_n]],
        }
    except:
        pass
    
    return result


# ============================================================
#  4. 技术指标批量计算
# ============================================================

def calc_technical_indicators(bars_df):
    """
    输入: mootdx bars DataFrame (必须有 close/high/low/vol 列)
    输出: dict of technical indicators
    """
    df = bars_df.copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["vol"].astype(float)

    cur = float(close.iloc[-1])
    n = len(close)

    # 均线
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma10 = float(close.rolling(10).mean().iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1]) if n >= 60 else 0
    ma120 = float(close.rolling(120).mean().iloc[-1]) if n >= 120 else 0

    # 均线斜率 (最近5日均线变化 / 价格)
    ma5_prev = float(close.rolling(5).mean().iloc[-6]) if n >= 6 else ma5
    ma5_slope = (ma5 / ma5_prev - 1) * 100 if ma5_prev > 0 else 0
    ma20_prev = float(close.rolling(20).mean().iloc[-6]) if n >= 25 else ma20
    ma20_slope = (ma20 / ma20_prev - 1) * 100 if ma20_prev > 0 else 0

    # 量比 (今日/前5日均量)
    v_today = float(vol.iloc[-1])
    v_5avg = float(vol.iloc[-6:-1].mean()) if n >= 6 else float(vol.mean())
    vr = v_today / v_5avg if v_5avg > 0 else 1.0

    # 量比趋势 (5日均量/20日均量)
    v_5avg_all = float(vol.iloc[-5:].mean())
    v_20avg = float(vol.iloc[-20:].mean()) if n >= 20 else v_5avg_all
    vr_trend = v_5avg_all / v_20avg if v_20avg > 0 else 1.0

    # stockstats 指标
    stock = StockDataFrame.retype(df)
    try:
        rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
    except:
        rsi6 = 50
    try:
        rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
    except:
        rsi14 = 50
    try:
        dif = float(stock["macd"].dropna().iloc[-1])
        dea = float(stock["macds"].dropna().iloc[-1])
        macdh = float(stock["macdh"].dropna().iloc[-1])
        macdh_prev = float(stock["macdh"].dropna().iloc[-2])
    except:
        dif = dea = macdh = macdh_prev = 0
    try:
        k = float(stock["kdjk"].dropna().iloc[-1])
        d_val = float(stock["kdjd"].dropna().iloc[-1])
        j = float(stock["kdjj"].dropna().iloc[-1])
    except:
        k = d_val = j = 50
    try:
        boll_u = float(stock["boll_ub"].dropna().iloc[-1])
        boll_m = float(stock["boll"].dropna().iloc[-1])
        boll_l = float(stock["boll_lb"].dropna().iloc[-1])
        boll_pos = (cur - boll_l) / (boll_u - boll_l) * 100 if (boll_u - boll_l) > 0 else 50
        boll_width = (boll_u - boll_l) / boll_m * 100 if boll_m > 0 else 10
    except:
        boll_u = boll_m = boll_l = cur
        boll_pos = 50
        boll_width = 10

    # 涨跌幅
    chg_3d = (cur / float(close.iloc[-4]) - 1) * 100 if n >= 4 else 0
    chg_5d = (cur / float(close.iloc[-6]) - 1) * 100 if n >= 6 else 0
    chg_10d = (cur / float(close.iloc[-11]) - 1) * 100 if n >= 11 else 0
    chg_20d = (cur / float(close.iloc[-21]) - 1) * 100 if n >= 21 else 0

    # 乖离
    dev = (cur / ma20 - 1) * 100 if ma20 > 0 else 0

    # 连涨/连跌
    up_days = 0
    down_days = 0
    for d in range(1, min(10, n)):
        if float(close.iloc[-d]) > float(close.iloc[-d - 1]):
            up_days += 1
        else:
            break
    for d in range(1, min(10, n)):
        if float(close.iloc[-d]) < float(close.iloc[-d - 1]):
            down_days += 1
        else:
            break

    # ATR (14日)
    tr_list = []
    for i in range(max(0, n - 14), n):
        hl = float(high.iloc[i]) - float(low.iloc[i])
        hc = abs(float(high.iloc[i]) - float(close.iloc[i - 1])) if i > 0 else hl
        lc = abs(float(low.iloc[i]) - float(close.iloc[i - 1])) if i > 0 else hl
        tr_list.append(max(hl, hc, lc))
    atr14 = np.mean(tr_list) if tr_list else 0

    # 相对强弱 RPS(20)
    chg_20d_indiv = (cur / float(close.iloc[-21]) - 1) * 100 if n >= 21 else 0
    # (指数对比在外部计算)

    # 涨停基因 (近20日涨停次数)
    limit_up_count = 0
    for d in range(20, 0, -1):
        if n > d + 1:
            today_c = float(close.iloc[-d])
            yesterday_c = float(close.iloc[-d - 1])
            if yesterday_c > 0:
                chg_day = (today_c / yesterday_c - 1) * 100
                if chg_day >= 9.5:
                    limit_up_count += 1

    return {
        "cur": cur, "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "ma120": ma120,
        "ma5_slope": ma5_slope, "ma20_slope": ma20_slope,
        "vr": vr, "vr_trend": vr_trend, "v_today": v_today, "v_5avg": v_5avg,
        "rsi6": rsi6, "rsi14": rsi14,
        "dif": dif, "dea": dea, "macdh": macdh, "macdh_prev": macdh_prev,
        "k": k, "d_val": d_val, "j": j,
        "boll_u": boll_u, "boll_m": boll_m, "boll_l": boll_l,
        "boll_pos": boll_pos, "boll_width": boll_width,
        "chg_3d": chg_3d, "chg_5d": chg_5d, "chg_10d": chg_10d, "chg_20d": chg_20d,
        "dev": dev, "up_days": up_days, "down_days": down_days,
        "atr14": atr14, "limit_up_count": limit_up_count,
    }


# ============================================================
#  5. 量价背离检测
# ============================================================

def detect_volume_price_divergence(close_series, vol_series, n=5):
    """
    检测量价背离
    返回: ("bull"|"bear"|None, score_adjustment)
    - "bull_divergence": 价格涨但量缩 = 多头背离 (危险信号)
    - "bear_divergence": 价格跌但量增 = 空头背离 (可能是抄底机会)
    """
    chg_short = (float(close_series.iloc[-1]) / float(close_series.iloc[-n]) - 1) * 100
    vol_short = float(vol_series.iloc[-n:].mean())
    vol_long = float(vol_series.iloc[-n * 2:-n].mean()) if len(vol_series) >= n * 2 else vol_short
    vol_change = (vol_short / vol_long - 1) * 100 if vol_long > 0 else 0

    if chg_short > 2 and vol_change < -15:
        return "bull_divergence", -15  # 涨+缩量=危险
    elif chg_short > 1 and vol_change < -8:
        return "bull_divergence", -8
    elif chg_short < -2 and vol_change > 15:
        return "bear_divergence", -5  # 跌+放量=可能企稳（需结合下影线）
    elif chg_short < -1 and vol_change > 8:
        return "bear_divergence", -3

    return None, 0


# ============================================================
#  6. ATR 动态止损
# ============================================================

def calc_atr_stop(price, atr14):
    """返回止损百分比和止损价"""
    pct = (atr14 * 1.5) / price * 100 if price > 0 else 3
    pct = max(2.0, min(5.0, pct))
    return pct, price * (1 - pct / 100)


# ============================================================
#  7. 股票名称批量获取 (腾讯API)
# ============================================================

_name_cache = {}

def get_name_batch(codes, name_map=None):
    """批量获取股票名称，优先用 name_map"""
    result = {}
    missing = []
    for code in codes:
        if name_map and code in name_map:
            result[code] = name_map[code]
        elif code in _name_cache:
            result[code] = _name_cache[code]
        else:
            missing.append(code)

    if missing:
        for i in range(0, len(missing), 80):
            batch = missing[i:i + 80]
            try:
                url = "https://qt.gtimg.cn/q=" + ",".join(
                    [f"sz{c}" if c[0] in "023" else f"sh{c}" for c in batch])
                resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
                text = resp.content.decode("gbk", errors="replace")
                for code in batch:
                    prefix = "sz" if code[0] in "023" else "sh"
                    for line in text.split("\n"):
                        if f"v_{prefix}{code}" in line:
                            parts = line.split("~")
                            if len(parts) > 1:
                                result[code] = parts[1]
                                _name_cache[code] = parts[1]
            except:
                pass

    return result


# ============================================================
#  8. 行业信息
# ============================================================

_industry_cache = {}

def get_industry_batch(codes):
    """从 mootdx finance 获取行业信息"""
    c = get_client()
    result = {}
    for code in codes:
        if code in _industry_cache:
            result[code] = _industry_cache[code]
            continue
        try:
            f = c.finance(symbol=code)
            if f is not None and len(f) > 0 and "industry" in f.columns:
                industry_code = int(f.iloc[0]["industry"])
                # mootdx industry code mapping (常见)
                result[code] = industry_code
                _industry_cache[code] = industry_code
        except:
            pass
    return result


# ============================================================
#  9. 板块热度（简化：通过同花顺强势股题材统计）
# ============================================================

def get_hot_sectors():
    """获取今日热门题材"""
    try:
        from datetime import date
        d = date.today().strftime("%Y-%m-%d")
        url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{d}/orderby/date/orderway/desc/charset/GBK/"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        rows = data.get("data") or []
        tags = []
        for row in rows:
            reason = row.get("reason", "")
            for t in str(reason).split("+"):
                tags.append(t.strip())
        from collections import Counter
        return Counter(tags).most_common(20)
    except:
        return []


# ============================================================
# 10. 风险标签生成
# ============================================================

def generate_risk_tags(r):
    """统一的股票风险标签生成"""
    warnings = []
    if r.get("vr", 1) < 0.3:
        warnings.append("无量")
    elif r.get("vr", 1) < 0.5:
        warnings.append("缩量")
    if r.get("rsi14", 50) > 75:
        warnings.append("RSI超买")
    elif r.get("rsi6", 50) > 80:
        warnings.append("RSI过热")
    if r.get("dev", 0) > 25:
        warnings.append("乖离大")
    elif r.get("dev", 0) > 18:
        warnings.append("乖离偏高")
    if r.get("chg_5d", 0) > 12:
        warnings.append("5日透支")
    if r.get("up_days", 0) >= 4:
        warnings.append(f"连涨{r['up_days']}天")
    if r.get("down_days", 0) >= 4:
        warnings.append(f"连阴{r['down_days']}天")
    if r.get("j", 50) > 100:
        warnings.append("J超买")
    if r.get("price", 0) > 80:
        warnings.append("高价")
    turnover = r.get("turnover", 5)
    if turnover < 1:
        warnings.append("换手过低")
    elif turnover > 25:
        warnings.append("换手过高")
    main_net = r.get("main_net", 0)
    if main_net < -10000000:
        warnings.append("主力流出")
    elif main_net < -5000000:
        warnings.append("主力偏出")
    return warnings
