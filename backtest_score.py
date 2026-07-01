"""
多因子评分系统回测验证
对 10 只强势股做滚动窗口回测，验证评分是否与后续收益正相关。

方法：
  1. 每只股票拉 250 日 K 线
  2. 从第 60 天起，每个交易日计算当天技术评分
  3. 记录评分 + 未来 1/3/5/10 日的实际收益
  4. 按分数段统计胜率、平均收益、盈亏比
"""
import pandas as pd
import numpy as np
import time
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

STOCKS = [
    ("600516", "方大炭素"),
    ("688268", "华特气体"),
    ("002156", "通富微电"),
    ("600487", "亨通光电"),
    ("301366", "一博科技"),
    ("603236", "移远通信"),
    ("600688", "上海石化"),
    ("600121", "郑州煤电"),
    ("002965", "祥鑫科技"),
    ("688655", "迅捷兴"),
]

client = Quotes.factory(market='std')


def get_klines(code, days=250):
    """拉K线数据，返回 stockstats 对象 + close series"""
    bars = client.bars(symbol=code, category=4, offset=days)
    if bars is None or len(bars) < 100:
        return None, None
    df = pd.DataFrame(bars)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    stock = StockDataFrame.retype(df)
    return stock, df['close']


def calc_score_at(idx, close, stock):
    """
    在历史某个截面计算技术评分（复用 score_stocks.py 的 5 维评分逻辑）。
    idx: pandas 位置索引
    返回 (score, signals)
    """
    if idx < 20:
        return 0, []
    
    c = float(close.iloc[idx])
    vol_series = stock['volume'] if 'volume' in dir(stock) else close
    
    # --- 获取各指标的 idx 位置值 ---
    try:
        rsi = float(stock['rsi_14'].iloc[idx])
    except:
        rsi = 50
    try:
        dif = float(stock['macd'].iloc[idx])
        dea = float(stock['macds'].iloc[idx])
    except:
        dif = dea = 0
    try:
        k = float(stock['kdjk'].iloc[idx])
        d = float(stock['kdjd'].iloc[idx])
        j = float(stock['kdjj'].iloc[idx])
    except:
        k = d = j = 50
    
    ma5 = float(close.iloc[max(0, idx-4):idx+1].mean())
    ma10 = float(close.iloc[max(0, idx-9):idx+1].mean())
    ma20 = float(close.iloc[max(0, idx-19):idx+1].mean())
    ma60 = float(close.iloc[max(0, idx-59):idx+1].mean()) if idx >= 60 else None
    
    # 量比
    if idx >= 20:
        vol_recent = float(vol_series.iloc[max(0, idx-4):idx+1].mean()) if len(vol_series) > idx else 1
        vol_ref = float(vol_series.iloc[max(0, idx-19):max(0, idx-4)].mean()) if len(vol_series) > idx else 1
        vol_ratio = vol_recent / vol_ref if vol_ref > 0 else 1
    else:
        vol_ratio = 1.0

    score = 0
    signals = []

    # RSI (0-25)
    if rsi < 20:
        score += 25
        signals.append("RSI超卖")
    elif rsi < 30:
        score += 20
    elif 30 <= rsi <= 70:
        score += 18
    elif rsi > 80:
        score += 5
        signals.append("RSI超买")
    elif rsi > 70:
        score += 10

    # MACD (0-20)
    if dif > dea > 0:
        score += 20
    elif dif > dea:
        score += 12
    elif dif < dea < 0:
        score += 3
    else:
        score += 7

    # 均线 (0-25)
    if ma60 and c > ma5 > ma10 > ma20 > ma60:
        score += 25
    elif c > ma5 > ma10 > ma20:
        score += 20
    elif c > ma20:
        score += 12
    elif c < ma5 < ma10 < ma20:
        score += 3
    else:
        score += 8

    # 量价 (0-15)
    chg_5d = (c / float(close.iloc[max(0, idx-4)]) - 1) * 100 if idx >= 5 else 0
    if chg_5d > 0 and vol_ratio > 1.3:
        score += 15
    elif chg_5d > 0 and vol_ratio > 1.0:
        score += 10
    elif chg_5d < 0 and vol_ratio < 0.7:
        score += 10
    elif chg_5d > 3 and vol_ratio < 0.8:
        score += 3
    else:
        score += 6

    # KDJ (0-15)
    if j < 0:
        score += 15
    elif k > d and 20 < k < 80:
        score += 12
    elif j > 100:
        score += 3
    else:
        score += 7

    return score, signals


def backtest_single(code, name, forward_days=[1, 3, 5, 10]):
    """单只股票回测"""
    stock, close = get_klines(code, 250)
    if stock is None:
        return []
    
    records = []
    # 从第60天滚动到倒数第11天（留出最远 forward window）
    max_fwd = max(forward_days)
    for i in range(60, len(close) - max_fwd - 1):
        score, signals = calc_score_at(i, close, stock)
        current_price = float(close.iloc[i])
        
        rec = {'code': code, 'name': name, 'score': score, 'date': close.index[i]}
        for fwd in forward_days:
            if i + fwd < len(close):
                future_price = float(close.iloc[i + fwd])
                ret = (future_price / current_price - 1) * 100
                rec[f'ret_{fwd}d'] = round(ret, 2)
            else:
                rec[f'ret_{fwd}d'] = None
        
        if score > 0:
            records.append(rec)
    
    return records


def bucketize(score):
    """分数分桶"""
    if score >= 80:
        return "🟢≥80 强烈推荐"
    elif score >= 65:
        return "🟢65-79 推荐"
    elif score >= 50:
        return "🟡50-64 关注"
    elif score >= 35:
        return "⚪35-49 观望"
    else:
        return "🔴<35 回避"


# ===== 主流程 =====
print("=" * 75)
print("  多因子评分系统 · 回归验证（滚动窗口回测）")
print("  验证方法：历史截面评分 vs 未来 N 日实际收益")
print("=" * 75)

all_records = []
for code, name in STOCKS:
    print(f"  回测 {code} {name} ...")
    try:
        recs = backtest_single(code, name)
        all_records.extend(recs)
        time.sleep(0.3)
    except Exception as e:
        print(f"    ✗ 失败: {e}")

if not all_records:
    print("无数据，退出")
    exit()

df = pd.DataFrame(all_records)
df['bucket'] = df['score'].apply(bucketize)

print(f"\n  总样本数: {len(df)} 个截面")
print(f"  覆盖股票: {df['code'].nunique()} 只")
print(f"  日期范围: {df['date'].min().date()} ~ {df['date'].max().date()}")

# ===== 按分数段统计各持有期表现 =====
print(f"\n{'='*75}")
print(f"  分数段 vs 未来收益 统计表")
print(f"{'='*75}")

for fwd in [1, 3, 5, 10]:
    col = f'ret_{fwd}d'
    print(f"\n  ── 持有 {fwd} 日 ──")
    print(f"  {'分数段':<20}{'样本数':<8}{'胜率':<8}{'平均收益':<10}{'中位数':<10}{'最大收益':<10}{'最小收益':<10}{'盈亏比':<8}")
    print(f"  {'-'*70}")
    
    bucket_order = ["🟢≥80 强烈推荐", "🟢65-79 推荐", "🟡50-64 关注", "⚪35-49 观望", "🔴<35 回避"]
    
    for bucket in bucket_order:
        subset = df[df['bucket'] == bucket][col].dropna()
        if len(subset) == 0:
            continue
        
        n = len(subset)
        win_rate = (subset > 0).sum() / n * 100
        avg_ret = subset.mean()
        median_ret = subset.median()
        max_ret = subset.max()
        min_ret = subset.min()
        
        # 盈亏比：盈利样本平均 / |亏损样本平均|
        winners = subset[subset > 0]
        losers = subset[subset < 0]
        if len(winners) > 0 and len(losers) > 0:
            pl_ratio = winners.mean() / abs(losers.mean())
        else:
            pl_ratio = float('inf') if len(losers) == 0 else 0
        
        print(f"  {bucket:<20}{n:<8}{win_rate:<8.1f}{avg_ret:<10.2f}{median_ret:<10.2f}{max_ret:<10.2f}{min_ret:<10.2f}{pl_ratio:<8.2f}")

# ===== 相关性分析 =====
print(f"\n{'='*75}")
print(f"  评分与未来收益 Spearman 秩相关系数")
print(f"{'='*75}")
print(f"  {'持有期':<12}{'相关系数':<10}{'解释'}")
print(f"  {'-'*45}")

for fwd in [1, 3, 5, 10]:
    col = f'ret_{fwd}d'
    valid = df[[col, 'score']].dropna()
    if len(valid) > 10:
        # 使用 pearson 替代 spearman（无需 scipy）
        corr = valid['score'].corr(valid[col], method='pearson')
        # 计算排名相关性（手动）
        rank_corr = valid['score'].rank().corr(valid[col].rank())
        if rank_corr > 0.10:
            interp = "显著正相关 ✓"
        elif rank_corr > 0.03:
            interp = "弱正相关"
        elif rank_corr > -0.03:
            interp = "基本无关"
        else:
            interp = "负相关 ✗"
        print(f"  {f'未来{fwd}日':<12}{rank_corr:<10.4f}{interp}")

# ===== 胜率随分数变化趋势 =====
print(f"\n{'='*75}")
print(f"  评分-胜率单调性检验（分数每提高5分，胜率应逐步上升）")
print(f"{'='*75}")

df['score_rounded'] = (df['score'] // 5) * 5
for fwd in [3, 5]:
    col = f'ret_{fwd}d'
    print(f"\n  ── 持有 {fwd} 日 ──")
    print(f"  {'分数':<8}{'样本数':<8}{'胜率%':<10}{'平均收益%':<12}")
    print(f"  {'-'*35}")
    for s in sorted(df['score_rounded'].unique()):
        subset = df[(df['score_rounded'] == s)][col].dropna()
        if len(subset) < 10:
            continue
        n = len(subset)
        wr = (subset > 0).sum() / n * 100
        ar = subset.mean()
        bar = '█' * int(wr // 5) if wr > 0 else ''
        print(f"  {s:<8}{n:<8}{wr:<10.1f}{ar:<12.2f}{bar}")

# ===== 结论 =====
print(f"\n{'='*75}")
print(f"  验证结论")
print(f"{'='*75}")

# 取≥65分 vs <50分的胜率差
ret_5d = df['ret_5d'].dropna()
high_score = df[df['score'] >= 65]
low_score = df[df['score'] < 50]

if len(high_score) > 10 and len(low_score) > 10:
    high_wr = (high_score['ret_5d'] > 0).sum() / len(high_score) * 100
    low_wr = (low_score['ret_5d'] > 0).sum() / len(low_score) * 100
    high_avg = high_score['ret_5d'].mean()
    low_avg = low_score['ret_5d'].mean()
    
    print(f"  高分段(≥65) 5日胜率: {high_wr:.1f}%  平均收益: {high_avg:+.2f}%")
    print(f"  低分段(<50) 5日胜率: {low_wr:.1f}%  平均收益: {low_avg:+.2f}%")
    print(f"  胜率差值: {high_wr - low_wr:+.1f}%  收益差值: {high_avg - low_avg:+.2f}%")
else:
    print("  样本不足，无法计算对比")

print(f"\n  ⚠ 以上仅为历史统计规律，不代表未来表现。投资有风险，入市需谨慎。")
