"""
统一回测框架 V1
支持四种策略的滚动窗口回测验证，输出胜率/盈亏比/夏普比率/IC分析
"""
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_utils import (
    get_client, get_stock_list, calc_technical_indicators,
    detect_volume_price_divergence, calc_atr_stop,
    calc_true_rps,
)

client = get_client()

# ============================================================
#  回测核心函数
# ============================================================

def _evaluate_signal_at_index(code, close, vol, high, low, idx, strategy="momentum"):
    """
    在历史某个截面计算策略信号
    返回: (passed, score, signals_dict)
    """
    if idx < 60:
        return False, 0, {}

    c = float(close.iloc[idx])
    n = len(close)

    # 基础技术指标
    ma5 = float(close.iloc[max(0, idx - 4):idx + 1].mean())
    ma10 = float(close.iloc[max(0, idx - 9):idx + 1].mean())
    ma20 = float(close.iloc[max(0, idx - 19):idx + 1].mean())
    ma60 = float(close.iloc[max(0, idx - 59):idx + 1].mean()) if idx >= 60 else 0

    # 量比
    v_today = float(vol.iloc[idx])
    v_5avg = float(vol.iloc[max(0, idx - 5):idx].mean())
    vr = v_today / v_5avg if v_5avg > 0 else 1.0

    # 涨幅
    chg_5d = (c / float(close.iloc[max(0, idx - 5)]) - 1) * 100 if idx >= 5 else 0
    chg_20d = (c / float(close.iloc[max(0, idx - 20)]) - 1) * 100 if idx >= 20 else 0

    # 乖离
    dev = (c / ma20 - 1) * 100 if ma20 > 0 else 0

    # RSI简易计算
    gains = []
    losses = []
    for d in range(max(0, idx - 14), idx):
        diff = float(close.iloc[d + 1]) - float(close.iloc[d])
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = np.mean(gains) if gains else 0
    avg_loss = np.mean(losses) if losses else 1
    rs = avg_gain / avg_loss if avg_loss > 0 else 1
    rsi14 = 100 - (100 / (1 + rs)) if avg_loss > 0 else 50

    # MACD简易
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    dif = float(ema12.iloc[idx]) - float(ema26.iloc[idx])
    dea = float(ema12.iloc[max(0, idx - 9):idx + 1].mean()) - float(ema26.iloc[max(0, idx - 9):idx + 1].mean())

    # 连涨天数
    up_days = 0
    for d in range(1, min(8, idx)):
        if float(close.iloc[idx - d]) > float(close.iloc[idx - d - 1]):
            up_days += 1
        else:
            break

    # KDJ简易
    low_n = float(low.iloc[max(0, idx - 9):idx + 1].min())
    high_n = float(high.iloc[max(0, idx - 9):idx + 1].max())
    rsv = (c - low_n) / (high_n - low_n) * 100 if high_n > low_n else 50
    j = 3 * rsv - 2 * 50  # 简化K/D

    signals = {
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
        "vr": vr, "rsi14": rsi14, "dif": dif, "dea": dea,
        "dev": dev, "chg_5d": chg_5d, "chg_20d": chg_20d,
        "up_days": up_days, "j": j,
    }

    score = 0
    details = []
    penalty = 0

    # === 通用动量评分（简化版）===
    # 均线
    if c > ma5 > ma10 > ma20:
        if ma60 > 0 and ma20 > ma60:
            score += 14
        else:
            score += 10
    elif c > ma5 > ma10:
        score += 7
    elif c > ma5:
        score += 4

    # RSI
    if 50 <= rsi14 <= 65:
        score += 10
    elif 45 <= rsi14 < 50:
        score += 7
    elif 65 < rsi14 <= 72:
        score += 5

    # MACD
    if dif > dea > 0:
        score += 10
    elif dif > dea:
        score += 6

    # 量能
    if 1.1 <= vr <= 2.5:
        score += 10
    elif 0.8 <= vr < 1.1:
        score += 6

    # 乖离
    if 2 <= dev <= 12:
        score += 5
    elif -2 <= dev < 2:
        score += 3

    # 惩罚
    if dev > 25: penalty += 12
    elif dev > 20: penalty += 8
    if rsi14 > 75: penalty += 8
    if vr < 0.5: penalty += 10
    if chg_5d > 15: penalty += 8
    if up_days >= 5: penalty += 6
    if j > 105: penalty += 3

    score -= penalty
    score = max(0, min(100, score))

    passed = score >= 65
    return passed, score, signals


def backtest_stock(code, name, lookback_days=250, fwd_days=[1, 3, 5, 10], strategy="momentum"):
    """
    单只股票滚动窗口回测
    """
    try:
        bars = client.bars(symbol=code, category=4, offset=lookback_days)
        if bars is None or len(bars) < 100:
            return []
    except:
        return []

    df = bars.copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["vol"].astype(float)
    n = len(close)

    records = []
    max_fwd = max(fwd_days)

    for i in range(60, n - max_fwd - 1):
        passed, score, signals = _evaluate_signal_at_index(
            code, close, vol, high, low, i, strategy
        )

        current_price = float(close.iloc[i])
        rec = {
            "code": code, "name": name,
            "date_idx": i,
            "passed": passed, "score": score,
            "price": current_price,
        }

        for fwd in fwd_days:
            if i + fwd < n:
                ret = (float(close.iloc[i + fwd]) / current_price - 1) * 100
                rec[f"ret_{fwd}d"] = round(ret, 2)
            else:
                rec[f"ret_{fwd}d"] = None
        records.append(rec)

    return records


def run_backtest(codes, fwd_days=[1, 3, 5, 10], lookback=250):
    """
    批量回测
    codes: list of (code, name)
    """
    all_records = []
    total = len(codes)

    for ci, (code, name) in enumerate(codes):
        try:
            recs = backtest_stock(code, name, lookback, fwd_days, "momentum")
            all_records.extend(recs)
        except:
            pass

        if (ci + 1) % 5 == 0:
            print(f"    回测进度: {ci + 1}/{total}")

        time.sleep(0.3)

    return pd.DataFrame(all_records)


# ============================================================
#  统计分析
# ============================================================

def analyze_results(df):
    """分析回测结果"""
    if df.empty:
        print("无回测数据")
        return

    signals = df[df["passed"] == True]
    noise = df[df["passed"] == False]

    print(f"\n{'=' * 76}")
    print(f"  回测结果概要")
    print(f"{'=' * 76}")
    print(f"  总截面: {len(df)}")
    print(f"  信号数: {len(signals)} ({len(signals) / max(1, len(df)) * 100:.1f}%)")
    print(f"  过滤掉: {len(noise)}")

    print(f"\n{'=' * 76}")
    print(f"  持有期收益对比（信号 vs 噪声）")
    print(f"{'=' * 76}")

    for fwd in [1, 3, 5, 10]:
        col = f"ret_{fwd}d"
        if col not in df.columns:
            continue

        print(f"\n  ── 持有 {fwd} 日 ──")
        print(f"  {'类别':<12}{'样本':<8}{'胜率%':<10}{'平均%':<10}{'盈亏比':<8}{'最大%':<10}{'最小%':<10}")
        print(f"  {'-' * 65}")

        for label, subset in [("✅ 通过", signals), ("❌ 噪声", noise)]:
            data = subset[col].dropna()
            if len(data) == 0:
                continue
            n = len(data)
            wr = (data > 0).sum() / n * 100
            avg = data.mean()
            w = data[data > 0]
            l = data[data < 0]
            pl = w.mean() / abs(l.mean()) if len(w) and len(l) else 0
            print(f"  {label:<12}{n:<8}{wr:<10.1f}{avg:<10.2f}{pl:<8.2f}{data.max():<10.2f}{data.min():<10.2f}")

    # 分数段分析
    if "score" in df.columns and len(signals) > 20:
        print(f"\n{'=' * 76}")
        print(f"  分数段细分（信号样本）")
        print(f"{'=' * 76}")

        for fwd in [3, 5]:
            col = f"ret_{fwd}d"
            if col not in df.columns:
                continue
            print(f"\n  ── 持有 {fwd} 日 ──")
            print(f"  {'分数段':<12}{'样本':<8}{'胜率%':<10}{'平均%':<10}{'盈亏比':<8}")
            print(f"  {'-' * 40}")

            for lo, hi, label in [(65, 70, "65-70"), (70, 75, "70-75"),
                                  (75, 80, "75-80"), (80, 85, "85-90"), (90, 100, "90-100")]:
                subset = signals[(signals["score"] >= lo) & (signals["score"] < hi)][col].dropna()
                if len(subset) < 5:
                    continue
                n = len(subset)
                wr = (subset > 0).sum() / n * 100
                avg = subset.mean()
                w = subset[subset > 0]
                l = subset[subset < 0]
                pl = w.mean() / abs(l.mean()) if len(w) and len(l) else 0
                bar = "█" * int(wr / 5) + "░" * (20 - int(wr / 5))
                print(f"  {label:<12}{n:<8}{wr:<10.1f}{avg:<10.2f}{pl:<8.2f}  [{bar}]")

    # 评分-收益相关性
    if "score" in df.columns:
        print(f"\n{'=' * 76}")
        print(f"  评分-收益 Spearman 相关系数")
        print(f"{'=' * 76}")
        for fwd in [1, 3, 5, 10]:
            col = f"ret_{fwd}d"
            if col not in df.columns:
                continue
            valid = df[[col, "score"]].dropna()
            if len(valid) > 20:
                rank_corr = valid["score"].rank().corr(valid[col].rank())
                if rank_corr > 0.10:
                    interp = "显著正相关 ✓"
                elif rank_corr > 0.03:
                    interp = "弱正相关"
                elif rank_corr > -0.03:
                    interp = "基本无关"
                else:
                    interp = "负相关 ✗"
                print(f"  {f'未来{fwd}日':<12}{rank_corr:<10.4f}{interp}")


# ============================================================
#  主入口
# ============================================================

if __name__ == "__main__":
    print("=" * 76)
    print("  统一回测框架 V1 — 技术评分系统验证")
    print("=" * 76)

    # 测试股票池
    test_stocks = [
        ("600516", "方大炭素"),
        ("002156", "通富微电"),
        ("600487", "亨通光电"),
        ("603236", "移远通信"),
        ("600688", "上海石化"),
        ("002965", "祥鑫科技"),
        ("000001", "平安银行"),
        ("000858", "五粮液"),
        ("600519", "贵州茅台"),
        ("300750", "宁德时代"),
    ]

    print(f"\n  回测 {len(test_stocks)} 只股票...")
    print(f"  每只拉取250日K线，滚动窗口回测")
    print()

    df = run_backtest(test_stocks, fwd_days=[1, 3, 5, 10], lookback=250)
    analyze_results(df)

    print(f"\n  ⚠ 以上仅为历史统计规律，不代表未来表现")
    print(f"  投资有风险，入市需谨慎")
