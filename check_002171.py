"""楚江新材 002171 实时深度分析"""
import pandas as pd
import numpy as np
import logging
logging.getLogger("tdxpy").setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import requests

client = Quotes.factory(market="std")
UA = "Mozilla/5.0"

CODE = "002171"
NAME = "楚江新材"

bars = client.bars(symbol=CODE, category=4, offset=120)
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

ma5 = float(close.rolling(5).mean().iloc[-1])
ma10 = float(close.rolling(10).mean().iloc[-1])
ma20 = float(close.rolling(20).mean().iloc[-1])
ma60 = float(close.rolling(60).mean().iloc[-1])
ma120 = float(close.rolling(120).mean().iloc[-1]) if len(close) >= 120 else None

v5 = float(vol.iloc[-5:].mean())
v10 = float(vol.iloc[-10:].mean())
v20 = float(vol.iloc[-20:].mean())

try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
except: rsi6 = 50
try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
except: rsi14 = 50

try:
    dif = float(stock["macd"].dropna().iloc[-1])
    dea = float(stock["macds"].dropna().iloc[-1])
    macdh = float(stock["macdh"].dropna().iloc[-1])
    macdh_p = float(stock["macdh"].dropna().iloc[-2])
    macdh_p3 = float(stock["macdh"].dropna().iloc[-4])
except: dif=dea=macdh=macdh_p=macdh_p3=0

try:
    k = float(stock["kdjk"].dropna().iloc[-1])
    d_val = float(stock["kdjd"].dropna().iloc[-1])
    j = float(stock["kdjj"].dropna().iloc[-1])
except: k=d_val=j=50

try:
    boll_m = float(stock["boll"].dropna().iloc[-1])
    boll_u = float(stock["boll_ub"].dropna().iloc[-1])
    boll_l = float(stock["boll_lb"].dropna().iloc[-1])
except: boll_m=boll_u=boll_l=0

chg_today = (c / prev_c - 1) * 100
chg_3d = (c / float(close.iloc[-3]) - 1) * 100 if len(close) >= 3 else 0
chg_5d = (c / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
chg_10d = (c / float(close.iloc[-10]) - 1) * 100 if len(close) >= 10 else 0
chg_20d = (c / float(close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0
dev = (c / ma20 - 1) * 100

amplitude = (h / l - 1) * 100
upper_shadow = (h - max(c, o)) / o * 100
lower_shadow = (min(c, o) - l) / o * 100
body_pct = (c - o) / o * 100

n_up = 0
for i in range(1, 10):
    if len(close) > i and close.iloc[-i] > close.iloc[-(i+1)]:
        n_up += 1
    else:
        break

high_20 = float(close.iloc[-20:].max())
low_20 = float(close.iloc[-20:].min())
pct_h = (c / high_20 - 1) * 100
pct_l = (c / low_20 - 1) * 100

# 腾讯实时
try:
    r = requests.get("https://qt.gtimg.cn/q=sz002171", headers={"User-Agent": UA}, timeout=10)
    parts = r.content.decode("gbk").split("~")
    turnover = parts[38] if len(parts) > 38 else "N/A"
    pe = parts[39] if len(parts) > 39 else "N/A"
    amount_str = parts[37] if len(parts) > 37 else "N/A"
except:
    turnover = pe = amount_str = "N/A"

# 同花顺题材
try:
    r2 = requests.get("http://zx.10jqka.com.cn/event/api/getharden/date/2026-06-05/orderby/date/orderway/desc/charset/GBK/",
                      headers={"User-Agent": UA}, timeout=10)
    reason_str = "未上榜"
    for item in r2.json().get("data", []):
        if str(item.get("code", "")).zfill(6) == "002171":
            reason_str = str(item.get("reason", ""))
            break
except:
    reason_str = "获取失败"

# === 输出 ===
print("=" * 68)
print(f"  {NAME} (002171) 实时深度分析")
print("=" * 68)
print()
print("  【行情】")
print(f"  现价: ¥{c:.2f}    今开: ¥{o:.2f}    昨收: ¥{prev_c:.2f}")
print(f"  最高: ¥{h:.2f}    最低: ¥{l:.2f}    振幅: {amplitude:.1f}%")
print(f"  今日: {chg_today:+.1f}%    实体: {body_pct:+.1f}%")
print(f"  上影: {upper_shadow:.1f}%    下影: {lower_shadow:.1f}%")
print(f"  换手: {turnover}%    PE: {pe}")
print(f"  题材: {reason_str}")

print()
print("  【均线】")
ma_status = ""
if c > ma5 > ma10 > ma20:
    if ma60 and ma20 > ma60:
        ma_status = "完美多头排列 ✅"
    else:
        ma_status = "短期多头排列 ✅"
elif c > ma5 > ma10:
    ma_status = "站上MA5/MA10"
elif c > ma5:
    ma_status = "站上MA5"
else:
    ma_status = "偏弱"

print(f"  MA5:  ¥{ma5:.2f}    MA10: ¥{ma10:.2f}    MA20: ¥{ma20:.2f}    MA60: ¥{ma60:.2f}")
if ma120: print(f"  MA120: ¥{ma120:.2f}")
print(f"  乖离(MA20): {dev:.1f}%    均线发散度: {(ma5/ma20-1)*100:.1f}%")
print(f"  状态: {ma_status}")

print()
print("  【指标】")
rsi_st = "健康" if 55 <= rsi14 <= 68 else ("偏高" if rsi14 > 72 else "偏弱")
print(f"  RSI(6): {rsi6:.1f}    RSI(14): {rsi14:.1f}  [{rsi_st}]")

macd_st = "多头加速" if dif>dea>0 and macdh>macdh_p else ("多头" if dif>dea>0 else ("死叉" if dif<dea else "粘合"))
print(f"  MACD: DIF={dif:.3f}  DEA={dea:.3f}  柱={macdh:.3f}  [{macd_st}]")
print(f"  KDJ:  K={k:.1f}  D={d_val:.1f}  J={j:.1f}")
if boll_u > 0:
    boll_pos = (c - boll_l) / (boll_u - boll_l) * 100
    boll_st = "上轨附近" if boll_pos > 90 else ("中轨上方" if boll_pos > 50 else "中轨下方")
    print(f"  BOLL: 上={boll_u:.2f} 中={boll_m:.2f} 下={boll_l:.2f}  位置={boll_pos:.0f}% [{boll_st}]")

print()
print("  【量能】")
v_st = "放量" if v5/v20 > 1.5 else ("温和放量" if v5/v20 > 1.2 else ("缩量" if v5/v20 < 0.8 else "正常"))
print(f"  5日均量: {v5/10000:.0f}万    20日均量: {v20/10000:.0f}万    量比: {v5/v20:.2f}x [{v_st}]")

print()
print("  【涨跌】")
print(f"  今日: {chg_today:+.1f}%    3日: {chg_3d:+.1f}%    5日: {chg_5d:+.1f}%    10日: {chg_10d:+.1f}%    20日: {chg_20d:+.1f}%")
print(f"  连续阳线: {n_up}日    距20日高: {pct_h:.1f}%    距20日低: +{pct_l:.1f}%")

# 近5日K线
print()
print("  【近5日K线】")
for i in range(-4, 1):
    idx = i
    dt = str(close.index[idx].date())
    c_i = float(close.iloc[idx])
    o_i = float(df["open"].iloc[idx])
    chg_i = (c_i / float(close.iloc[idx-1]) - 1) * 100
    color = "阳" if c_i >= o_i else "阴"
    mark = " ←今日" if i == -1 else ""
    print(f"  {dt}  {chg_i:+.2f}%  {color}{mark}")

# 综合评分
print()
print("=" * 68)
print("  3-5%策略评分")
print("=" * 68)

score = 0
details = []

# 均线 20
if c > ma5 > ma10 > ma20 and ma60 and ma20 > ma60:
    score += 20; details.append(("均线完美多头(MA5>10>20>60)", 20))
elif c > ma5 > ma10 > ma20:
    score += 17; details.append(("短期多头排列", 17))
else:
    s = 12 if c > ma5 > ma10 else 7
    score += s; details.append(("均线一般", s))

# RSI 20
if 52 <= rsi14 <= 65:
    score += 20; details.append((f"RSI={rsi14:.0f}健康", 20))
elif 45 <= rsi14 < 52:
    score += 14; details.append((f"RSI={rsi14:.0f}偏弱", 14))
elif 65 < rsi14 <= 72:
    score += 12; details.append((f"RSI={rsi14:.0f}偏高", 12))
else:
    score += 6; details.append((f"RSI={rsi14:.0f}", 6))

# MACD 15
if dif > dea > 0 and macdh > macdh_p:
    score += 15; details.append(("MACD多头加速", 15))
elif dif > dea > 0:
    score += 12; details.append(("MACD多头", 12))
elif dif > dea:
    score += 8; details.append(("MACD金叉", 8))
else:
    score += 4; details.append(("MACD一般", 4))

# 量能 15
vr = v5/v20
if 1.2 <= vr <= 2.5:
    score += 15; details.append((f"量比{vr:.1f}x", 15))
elif 1.0 <= vr < 1.2:
    score += 10; details.append((f"量比{vr:.1f}x", 10))
elif vr > 2.5:
    score += 10; details.append(("放量过大", 10))
else:
    score += 5; details.append((f"量比{vr:.1f}x", 5))

# 乖离 10
if 2 <= dev <= 12:
    score += 10; details.append((f"乖离{dev:.0f}%", 10))
elif dev < 2:
    score += 7; details.append((f"乖离{dev:.0f}%", 7))
elif 12 < dev <= 18:
    score += 6; details.append((f"乖离{dev:.0f}%", 6))
else:
    score += 3; details.append((f"乖离{dev:.0f}%", 3))

# 涨幅适中 10
if 3 <= chg_today <= 5:
    score += 10; details.append((f"今日+{chg_today:.1f}%", 10))
elif 1 <= chg_today <= 7:
    score += 7; details.append((f"今日+{chg_today:.1f}%", 7))

# 上影线扣分
penalty = 0
if upper_shadow > 3:
    penalty = min(5, int(upper_shadow))
    score -= penalty

if j > 100:
    score -= 3; penalty += 3

for d, pts in details:
    bar = "#" * (pts // 2) + "-" * (10 - pts // 2)
    print(f"  {d:<22} +{pts:<3} [{bar}]")
if penalty:
    print(f"  {'风险扣分':<22} -{penalty:<3}")

bar = "#"*int(score/5) + "-"*(20-int(score/5))
lvl = "强势买入" if score >= 85 else ("推荐" if score >= 70 else ("关注" if score >= 55 else "观望"))
print(f"  {'─'*42}")
print(f"  总评: {score}/100  [{bar}]  → {lvl}")

print()
print(f"  买入: 今日 ¥{c:.2f} 尾盘介入")
print(f"  目标: ¥{c*1.04:.2f}(+4%) ~ ¥{c*1.05:.2f}(+5%)")
print(f"  止损: ¥{c*0.98:.2f}(-2%)")
print(f"  ⚠ 不构成投资建议")
