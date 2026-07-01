"""深度对比分析 TOP 候选股"""
import pandas as pd
import numpy as np
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import time

CANDIDATES = [
    ("600516", "方大炭素", "石墨电极龙头+电池材料+核电石墨"),
    ("002613", "北玻股份", "玻璃深加工+钙钛矿设备+建筑节能"),
    ("600382", "广东明珠", "尾矿回收钨锡+铁精粉扩产+业绩补偿推进"),
    ("600063", "皖维高新", "MLCC+聚乙烯醇+国企"),
    ("603135", "中重科技", "机器人+出海+新增订单+到期赎回"),
]

client = Quotes.factory(market="std")

def deep_analysis(code):
    """多周期深度分析"""
    for period_name, offset in [("60日", 60), ("120日", 120)]:
        pass
    
    bars = client.bars(symbol=code, category=4, offset=120)
    if bars is None or len(bars) < 60:
        return None
    df = pd.DataFrame(bars)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    stock = StockDataFrame.retype(df)
    close = df["close"]
    vol = df["vol"]
    
    c = float(close.iloc[-1])
    o = float(df["open"].iloc[-1])
    h = float(df["high"].iloc[-1])
    l = float(df["low"].iloc[-1])
    prev_c = float(close.iloc[-2])
    
    # 均线
    ma5 = float(close.rolling(5).mean().iloc[-1])
    ma10 = float(close.rolling(10).mean().iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])
    ma120 = float(close.rolling(120).mean().iloc[-1]) if len(close) >= 120 else None
    
    # 量能
    v5 = float(vol.iloc[-5:].mean())
    v10 = float(vol.iloc[-10:].mean())
    v20 = float(vol.iloc[-20:].mean())
    
    # RSI
    try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
    except: rsi14 = 50
    try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
    except: rsi6 = rsi14
    
    # MACD
    try:
        dif = float(stock["macd"].dropna().iloc[-1])
        dea = float(stock["macds"].dropna().iloc[-1])
        macdh = float(stock["macdh"].dropna().iloc[-1])
        macdh_prev = float(stock["macdh"].dropna().iloc[-2])
        macdh_prev3 = float(stock["macdh"].dropna().iloc[-4]) if len(stock["macdh"].dropna()) >= 4 else 0
    except:
        dif=dea=macdh=macdh_prev=macdh_prev3=0
    
    # KDJ
    try:
        k = float(stock["kdjk"].dropna().iloc[-1])
        d_val = float(stock["kdjd"].dropna().iloc[-1])
        j = float(stock["kdjj"].dropna().iloc[-1])
    except:
        k=d_val=j=50
    
    # BOLL
    try:
        boll_mid = float(stock["boll"].dropna().iloc[-1])
        boll_ub = float(stock["boll_ub"].dropna().iloc[-1])
        boll_lb = float(stock["boll_lb"].dropna().iloc[-1])
        boll_width = (boll_ub - boll_lb) / boll_mid * 100
        boll_pos = (c - boll_lb) / (boll_ub - boll_lb) * 100
    except:
        boll_mid=boll_ub=boll_lb=boll_width=boll_pos=0
    
    # 涨跌幅
    chg_today = (c / prev_c - 1) * 100
    chg_3d = (c / float(close.iloc[-3]) - 1) * 100 if len(close) >= 3 else 0
    chg_5d = (c / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
    chg_10d = (c / float(close.iloc[-10]) - 1) * 100 if len(close) >= 10 else 0
    chg_20d = (c / float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0
    
    # K线形态
    body = (c - o) / o * 100
    upper_shadow = (h - max(c, o)) / o * 100
    lower_shadow = (min(c, o) - l) / o * 100
    amplitude = (h - l) / l * 100
    
    # 连续N日
    n_up = 0
    for i in range(1, 10):
        if len(close) > i and close.iloc[-i] > close.iloc[-(i+1)]:
            n_up += 1
        else:
            break
    
    # 20日最高/最低
    high_20 = float(close.iloc[-20:].max())
    low_20 = float(close.iloc[-20:].min())
    pct_from_high = (c / high_20 - 1) * 100
    pct_from_low = (c / low_20 - 1) * 100
    
    # 均线发散度（多头排列时 MA5偏离MA20的程度）
    ma_divergence = (ma5 / ma20 - 1) * 100
    
    result = {
        "c": c, "o": o, "h": h, "l": l, "prev_c": prev_c,
        "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "ma120": ma120,
        "v5": v5, "v10": v10, "v20": v20,
        "rsi6": rsi6, "rsi14": rsi14,
        "dif": dif, "dea": dea, "macdh": macdh, "macdh_prev": macdh_prev, "macdh_prev3": macdh_prev3,
        "k": k, "d_val": d_val, "j": j,
        "boll_mid": boll_mid, "boll_ub": boll_ub, "boll_lb": boll_lb, "boll_width": boll_width, "boll_pos": boll_pos,
        "chg_today": chg_today, "chg_3d": chg_3d, "chg_5d": chg_5d, "chg_10d": chg_10d, "chg_20d": chg_20d,
        "body": body, "upper_shadow": upper_shadow, "lower_shadow": lower_shadow, "amplitude": amplitude,
        "n_up": n_up,
        "high_20": high_20, "low_20": low_20, "pct_from_high": pct_from_high, "pct_from_low": pct_from_low,
        "ma_divergence": ma_divergence,
    }
    return result

# === 对比输出 ===
print("=" * 80)
print("  候选股深度对比分析 · 周五买入 → 周一卖出")
print("=" * 80)

all_data = {}
for code, name, reason in CANDIDATES:
    print(f"  分析 {code} {name}...")
    try:
        data = deep_analysis(code)
        if data:
            all_data[(code, name, reason)] = data
        time.sleep(0.35)
    except Exception as e:
        print(f"    ✗ {e}")

print(f"\n{'='*80}")
print("  📊 一、行情与K线形态对比")
print(f"{'='*80}")
print(f"  {'指标':<22}", end="")
for (code, name, reason), d in all_data.items():
    print(f"{name:<10}", end="")
print()
print(f"  {'─'*22}", end="")
for _ in all_data:
    print(f"{'─'*10}", end="")
print()

rows = [
    ("现价", lambda d: f"¥{d['c']:.2f}"),
    ("今日涨跌", lambda d: f"{d['chg_today']:+.1f}%"),
    ("振幅", lambda d: f"{d['amplitude']:.1f}%"),
    ("K线实体", lambda d: f"{d['body']:+.1f}%"),
    ("上影线", lambda d: f"{d['upper_shadow']:.1f}%"),
    ("下影线", lambda d: f"{d['lower_shadow']:.1f}%"),
    ("连续阳线", lambda d: f"{d['n_up']}日"),
    ("距20日高", lambda d: f"{d['pct_from_high']:.1f}%"),
    ("距20日低", lambda d: f"{d['pct_from_low']:.1f}%"),
]
for label, fn in rows:
    print(f"  {label:<22}", end="")
    for d in all_data.values():
        print(f"{fn(d):<10}", end="")
    print()

print(f"\n{'='*80}")
print(f"  📈 二、均线系统对比")
print(f"{'='*80}")
print(f"  {'均线':<22}", end="")
for (code, name, reason), d in all_data.items():
    print(f"{name:<10}", end="")
print()
print(f"  {'─'*22}", end="")
for _ in all_data:
    print(f"{'─'*10}", end="")
print()

ma_rows = [
    ("MA5", lambda d: f"{d['ma5']:.2f}"),
    ("MA10", lambda d: f"{d['ma10']:.2f}"),
    ("MA20", lambda d: f"{d['ma20']:.2f}"),
    ("MA60", lambda d: f"{d['ma60']:.2f}"),
    ("MA120(半年线)", lambda d: f"{d['ma120']:.2f}" if d['ma120'] else "N/A"),
    ("均线发散度", lambda d: f"{d['ma_divergence']:.1f}%"),
]
for label, fn in ma_rows:
    print(f"  {label:<22}", end="")
    for d in all_data.values():
        print(f"{fn(d):<10}", end="")
    print()

# 多头排列状态
print(f"\n  {'多头排列':<22}", end="")
for d in all_data.values():
    status = []
    if d['c'] > d['ma5']: status.append("MA5✓")
    if d['ma5'] > d['ma10']: status.append("MA10✓")
    if d['ma10'] > d['ma20']: status.append("MA20✓")
    if d['ma60'] and d['ma20'] > d['ma60']: status.append("MA60✓")
    if d['ma120'] and d['ma60'] and d['ma60'] > d['ma120']: status.append("MA120✓")
    print(f"{'/'.join(status[:3]):<10}", end="")
print()

print(f"\n{'='*80}")
print(f"  📉 三、技术指标对比")
print(f"{'='*80}")
print(f"  {'指标':<22}", end="")
for (code, name, reason), d in all_data.items():
    print(f"{name:<10}", end="")
print()
print(f"  {'─'*22}", end="")
for _ in all_data:
    print(f"{'─'*10}", end="")
print()

ind_rows = [
    ("RSI(6)", lambda d: f"{d['rsi6']:.1f}"),
    ("RSI(14)", lambda d: f"{d['rsi14']:.1f}"),
    ("MACD DIF", lambda d: f"{d['dif']:.3f}"),
    ("MACD DEA", lambda d: f"{d['dea']:.3f}"),
    ("MACD 柱", lambda d: f"{d['macdh']:.3f}"),
    ("KDJ-K", lambda d: f"{d['k']:.1f}"),
    ("KDJ-D", lambda d: f"{d['d_val']:.1f}"),
    ("KDJ-J", lambda d: f"{d['j']:.1f}"),
    ("BOLL上轨", lambda d: f"{d['boll_ub']:.2f}"),
    ("BOLL中轨", lambda d: f"{d['boll_mid']:.2f}"),
    ("BOLL下轨", lambda d: f"{d['boll_lb']:.2f}"),
    ("BOLL位置%", lambda d: f"{d['boll_pos']:.0f}%"),
    ("BOLL带宽%", lambda d: f"{d['boll_width']:.1f}%"),
]
for label, fn in ind_rows:
    print(f"  {label:<22}", end="")
    for d in all_data.values():
        print(f"{fn(d):<10}", end="")
    print()

print(f"\n{'='*80}")
print(f"  📊 四、量能与涨跌幅对比")
print(f"{'='*80}")
print(f"  {'指标':<22}", end="")
for (code, name, reason), d in all_data.items():
    print(f"{name:<10}", end="")
print()
print(f"  {'─'*22}", end="")
for _ in all_data:
    print(f"{'─'*10}", end="")
print()

vol_rows = [
    ("5日均量(万)", lambda d: f"{d['v5']/10000:.0f}"),
    ("10日均量(万)", lambda d: f"{d['v10']/10000:.0f}"),
    ("20日均量(万)", lambda d: f"{d['v20']/10000:.0f}"),
    ("量比(5/20)", lambda d: f"{d['v5']/d['v20']:.2f}x" if d['v20'] > 0 else "N/A"),
    ("量比(5/10)", lambda d: f"{d['v5']/d['v10']:.2f}x" if d['v10'] > 0 else "N/A"),
    ("今日涨跌", lambda d: f"{d['chg_today']:+.1f}%"),
    ("3日涨跌", lambda d: f"{d['chg_3d']:+.1f}%"),
    ("5日涨跌", lambda d: f"{d['chg_5d']:+.1f}%"),
    ("10日涨跌", lambda d: f"{d['chg_10d']:+.1f}%"),
    ("20日涨跌", lambda d: f"{d['chg_20d']:+.1f}%"),
]
for label, fn in vol_rows:
    print(f"  {label:<22}", end="")
    for d in all_data.values():
        print(f"{fn(d):<10}", end="")
    print()

# ===== 综合打分 =====
print(f"\n{'='*80}")
print(f"  🏆 五、综合评分矩阵")
print(f"{'='*80}")

def calc_total_score(d):
    """精细化评分 0-100"""
    score = 0
    
    # 均线 (25分)
    ma_score = 0
    if d['c'] > d['ma5'] > d['ma10'] > d['ma20']:
        ma_score = 25
    elif d['c'] > d['ma5'] > d['ma10']:
        ma_score = 18
    elif d['c'] > d['ma5']:
        ma_score = 10
    elif d['c'] < d['ma20']:
        ma_score = 0
    else:
        ma_score = 5
    score += ma_score
    
    # RSI (20分)
    rsi = d['rsi14']
    if 55 <= rsi <= 70:
        rsi_score = 20
    elif 50 <= rsi < 55:
        rsi_score = 15
    elif 70 < rsi <= 78:
        rsi_score = 12
    elif rsi > 78:
        rsi_score = 3
    elif 40 <= rsi < 50:
        rsi_score = 8
    else:
        rsi_score = 3
    score += rsi_score
    
    # MACD (15分)
    if d['dif'] > d['dea'] > 0 and d['macdh'] > d['macdh_prev']:
        macd_score = 15
    elif d['dif'] > d['dea'] > 0:
        macd_score = 12
    elif d['dif'] > d['dea']:
        macd_score = 8
    elif d['dif'] < d['dea']:
        macd_score = 2
    else:
        macd_score = 5
    score += macd_score
    
    # 量能 (15分)
    vol_ratio = d['v5'] / d['v20'] if d['v20'] > 0 else 1
    if vol_ratio > 1.8:
        vol_score = 15
    elif vol_ratio > 1.5:
        vol_score = 12
    elif vol_ratio > 1.2:
        vol_score = 10
    elif vol_ratio > 1.0:
        vol_score = 6
    elif vol_ratio > 0.8:
        vol_score = 3
    else:
        vol_score = 0
    score += vol_score
    
    # 乖离率 (10分)
    dev = (d['c'] / d['ma20'] - 1) * 100
    if 3 <= dev <= 12:
        dev_score = 10
    elif 0 <= dev < 3:
        dev_score = 7
    elif 12 < dev <= 18:
        dev_score = 7
    elif 18 < dev <= 25:
        dev_score = 4
    elif dev > 25:
        dev_score = 0
    else:
        dev_score = 3
    score += dev_score
    
    # 上影线风险 (5分, 扣分项)
    if d['upper_shadow'] > d['body'] * 0.5 and d['body'] > 0:
        upper_penalty = -5
    elif d['upper_shadow'] > 3:
        upper_penalty = -2
    else:
        upper_penalty = 0
    score += upper_penalty
    
    # 连阳加分 (5分)
    if d['n_up'] >= 5:
        streak = 5
    elif d['n_up'] >= 3:
        streak = 3
    elif d['n_up'] >= 2:
        streak = 2
    else:
        streak = 0
    score += streak
    
    # BOLL位置 (5分)
    if d['boll_pos'] > 0:
        if 50 <= d['boll_pos'] <= 95:
            boll_score = 5
        elif 30 <= d['boll_pos'] < 50:
            boll_score = 3
        elif d['boll_pos'] > 95:
            boll_score = 1  # 超涨扣分
        else:
            boll_score = 2
        score += boll_score
    
    return score

scored = []
for (code, name, reason), d in all_data.items():
    s = calc_total_score(d)
    scored.append((code, name, reason, d, s))

scored.sort(key=lambda x: x[4], reverse=True)

print(f"  {'排名':<5}{'代码':<10}{'名称':<10}{'均线':<6}{'RSI':<6}{'MACD':<6}{'量能':<6}{'乖离':<6}{'连阳':<6}{'总分':<6}{'建议'}")
print(f"  {'─'*75}")
for rank, (code, name, reason, d, total) in enumerate(scored):
    dev = (d['c'] / d['ma20'] - 1) * 100
    vol_ratio = d['v5'] / d['v20'] if d['v20'] > 0 else 1
    ma_ok = d['c'] > d['ma5'] > d['ma10'] > d['ma20']
    rsi_ok = 55 <= d['rsi14'] <= 75
    macd_ok = d['dif'] > d['dea'] > 0
    
    if total >= 85:
        rec = "🟢 强烈推荐"
    elif total >= 70:
        rec = "🟢 推荐"
    elif total >= 55:
        rec = "🟡 关注"
    elif total >= 40:
        rec = "⚪ 观望"
    else:
        rec = "🔴 回避"
    
    # 子项分数
    ma_s = 25 if d['c'] > d['ma5'] > d['ma10'] > d['ma20'] else (18 if d['c'] > d['ma5'] > d['ma10'] else (10 if d['c'] > d['ma5'] else 5))
    rsi_s = 20 if 55 <= d['rsi14'] <= 70 else (15 if 50 <= d['rsi14'] < 55 else (12 if 70 < d['rsi14'] <= 78 else 3))
    macd_s = 15 if d['dif'] > d['dea'] > 0 and d['macdh'] > d['macdh_prev'] else (12 if d['dif'] > d['dea'] > 0 else 8)
    vol_s = 15 if vol_ratio > 1.8 else (12 if vol_ratio > 1.5 else (10 if vol_ratio > 1.2 else 6))
    dev_s = 10 if 3 <= dev <= 12 else (7 if dev <= 18 else 4)
    
    print(f"  {rank+1:<5}{code:<10}{name:<10}{ma_s:<6}{rsi_s:<6}{macd_s:<6}{vol_s:<6}{dev_s:<6}{min(d['n_up'],5):<6}{total:<6}{rec}")

# ===== 最终结论 =====
print(f"\n{'='*80}")
print(f"  🎯 最终推荐")
print(f"{'='*80}")

best = scored[0]
code, name, reason, d, total = best

print(f"""
  首选: {name} ({code})  精密评分: {total}/100
  题材: {reason}

  核心优势:
""")

# 列出优势
advantages = []
if d['c'] > d['ma5'] > d['ma10'] > d['ma20']:
    advantages.append(f"  ✅ 均线完美多头排列: MA5({d['ma5']:.2f}) > MA10({d['ma10']:.2f}) > MA20({d['ma20']:.2f}) > MA60({d['ma60']:.2f})")
if 55 <= d['rsi14'] <= 70:
    advantages.append(f"  ✅ RSI(14)={d['rsi14']:.1f} 处于最佳攻击区间(55-70)")
if d['dif'] > d['dea'] > 0:
    advantages.append(f"  ✅ MACD DIF({d['dif']:.3f}) > DEA({d['dea']:.3f}) 多头且柱在放大")
vol_ratio = d['v5'] / d['v20'] if d['v20'] > 0 else 1
if vol_ratio > 1.2:
    advantages.append(f"  ✅ 量比 {vol_ratio:.1f}x，温和放量配合上涨")
dev = (d['c'] / d['ma20'] - 1) * 100
if 3 <= dev <= 15:
    advantages.append(f"  ✅ 乖离率 {dev:.1f}%，距MA20适中，未过度偏离")
if d['n_up'] >= 3:
    advantages.append(f"  ✅ 连续 {d['n_up']} 日收阳，多头趋势明确")

for adv in advantages:
    print(adv)

print(f"""
  风险提示:
  • 上影线 {d['upper_shadow']:.1f}%，{'较大，注意抛压' if d['upper_shadow'] > 3 else '正常'}
  • BOLL位置 {d['boll_pos']:.0f}%，{'短期超涨' if d['boll_pos'] > 95 else '健康'}
  • KDJ-J {d['j']:.1f}，{'接近超买' if d['j'] > 95 else '正常'}
  • 距20日高点 {d['pct_from_high']:.1f}%，{'接近前高压力' if d['pct_from_high'] > -3 else '有空间'}

  操作建议:
""")

target_7 = d['c'] * 1.07
target_10 = d['c'] * 1.10
stop_loss = d['c'] * 0.97

print(f"""
  买入: 今日盘中回踩 MA5(¥{d['ma5']:.2f})附近介入
  目标: ¥{target_7:.2f}(+7%) ~ ¥{target_10:.2f}(+10%)
  止损: ¥{stop_loss:.2f}(-3%)
  卖出: 周一收盘前必须出清
  仓位: ≤ 总资金 20%

  ⚠ 周末持仓注意: 政策/外盘/消息面风险
  ⚠ 以上为技术面分析，不构成投资建议
""")

if len(scored) >= 2:
    runner = scored[1]
    print(f"\n  备选: {runner[1]}({runner[0]})  评分: {runner[4]}")
    print(f"  题材: {runner[2]}")
