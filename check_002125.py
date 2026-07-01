"""湘潭电化 002125 实时技术面查询"""
import pandas as pd
import numpy as np
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import requests

client = Quotes.factory(market="std")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"

# === K线数据 ===
bars = client.bars(symbol="002125", category=4, offset=60)
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
prev_close = float(close.iloc[-2])
chg_pct = (c / prev_close - 1) * 100

ma5 = float(close.rolling(5).mean().iloc[-1])
ma10 = float(close.rolling(10).mean().iloc[-1])
ma20 = float(close.rolling(20).mean().iloc[-1])
ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else 0

v5 = float(vol.iloc[-5:].mean())
v20 = float(vol.iloc[-20:].mean())
vol_ratio = v5 / v20 if v20 > 0 else 1

chg_5d = (c / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
dev_20 = (c / ma20 - 1) * 100

# 技术指标
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
    boll_mid = float(stock["boll"].dropna().iloc[-1])
    boll_ub = float(stock["boll_ub"].dropna().iloc[-1])
    boll_lb = float(stock["boll_lb"].dropna().iloc[-1])
except:
    boll_mid = boll_ub = boll_lb = 0

amplitude = (h / l - 1) * 100

# 最近5天K线
recent = []
for i in range(-4, 1):
    idx = i
    o_i = float(df["open"].iloc[idx])
    c_i = float(close.iloc[idx])
    color_str = "阳" if c_i >= o_i else "阴"
    body = abs(c_i - o_i)
    date_str = str(close.index[idx].date())
    chg_i = (c_i / float(close.iloc[idx - 1]) - 1) * 100
    recent.append({"date": date_str, "chg": chg_i, "color": color_str, "body_pct": body / o_i * 100})

# 三连阳
is_sanyang = (
    close.iloc[-1] > close.iloc[-2]
    and close.iloc[-2] > close.iloc[-3]
    and close.iloc[-3] > close.iloc[-4]
)

# === 腾讯实时行情 ===
try:
    r = requests.get("https://qt.gtimg.cn/q=sz002125", headers={"User-Agent": UA}, timeout=10)
    raw = r.text
    parts = raw.split("~")
    turnover = parts[38] if len(parts) > 38 else "N/A"
    pe = parts[39] if len(parts) > 39 else "N/A"
except:
    turnover = "N/A"
    pe = "N/A"

# === 同花顺热点 ===
reason_str = "未上榜"
try:
    r2 = requests.get(
        "http://zx.10jqka.com.cn/event/api/getharden/date/2026-06-03/orderby/date/orderway/desc/charset/GBK/",
        headers={"User-Agent": UA},
        timeout=10,
    )
    hot_data = r2.json().get("data", [])
    for item in hot_data:
        if str(item.get("code", "")).zfill(6) == "002125":
            reason_str = str(item.get("reason", ""))
            break
except:
    pass

print("=" * 68)
print("  湘潭电化 (002125)  实时技术面")
print("=" * 68)

print()
print("  [行情]")
print(f"  最新: {c:.2f}    今开: {o:.2f}    昨收: {prev_close:.2f}")
print(f"  最高: {h:.2f}    最低: {l:.2f}    振幅: {amplitude:.1f}%")
print(f"  今日涨跌: {chg_pct:+.2f}%    5日涨跌: {chg_5d:+.1f}%")
print(f"  换手率: {turnover}%    PE: {pe}")

print()
print("  [均线系统]")
print(f"  MA5: {ma5:.2f}  |  MA10: {ma10:.2f}  |  MA20: {ma20:.2f}  |  MA60: {ma60:.2f}")
ma_status = (
    "多头排列(完美)"
    if c > ma5 > ma10 > ma20
    else ("站上MA5/MA10" if c > ma5 > ma10 else "需关注")
)
print(f"  乖离率(MA20): {dev_20:.1f}%    均线: {ma_status}")

print()
print("  [技术指标]")
# RSI
rsi_status = "强势" if 60 <= rsi14 <= 75 else ("过热!" if rsi14 > 80 else ("偏弱" if rsi14 < 40 else "中性"))
print(f"  RSI(14):  {rsi14:.1f}  [{rsi_status}]")

# MACD
if macdh > macdh_prev > 0:
    macd_status = "多头 + 柱放大(强)"
elif dif > dea:
    macd_status = "多头"
elif dif < dea:
    macd_status = "死叉"
else:
    macd_status = "粘合"
print(f"  MACD:    DIF={dif:.3f}  DEA={dea:.3f}  柱={macdh:.3f}  [{macd_status}]")

# KDJ
if k > d_val and j < 100:
    kdj_status = "金叉向上"
elif j > 100:
    kdj_status = "超买"
else:
    kdj_status = "正常"
print(f"  KDJ:     K={k:.1f}  D={d_val:.1f}  J={j:.1f}  [{kdj_status}]")

# BOLL
if boll_ub > 0:
    boll_width = (boll_ub - boll_lb) / boll_mid * 100
    boll_pos = (c - boll_lb) / (boll_ub - boll_lb) * 100
    if boll_pos > 90:
        boll_status = "上轨附近(压力)"
    elif boll_pos > 50:
        boll_status = "中轨上方"
    else:
        boll_status = "中轨下方"
    print(f"  BOLL:    上={boll_ub:.2f}  中={boll_mid:.2f}  下={boll_lb:.2f}  带宽={boll_width:.1f}%")
    print(f"           位置={boll_pos:.0f}% [{boll_status}]")

print()
print("  [量能]")
if vol_ratio > 1.5:
    vol_status = "放量"
elif vol_ratio > 1.2:
    vol_status = "温和放量"
elif vol_ratio < 0.8:
    vol_status = "缩量!"
else:
    vol_status = "正常"
print(f"  量比(5日/20日均): {vol_ratio:.2f}  [{vol_status}]")

print()
print("  [近5日K线]")
print(f"  {'日期':<14}{'涨跌':<10}{'阴/阳':<8}{'实体%':<10}")
print(f"  {'-'*42}")
for rk in recent:
    mark = " ←今日" if rk["date"] == str(close.index[-1].date()) else ""
    print(f"  {rk['date']:<14}{rk['chg']:+.2f}%     {rk['color']:<8}{rk['body_pct']:.1f}%{mark}")
print(f"  三连阳: {'是' if is_sanyang else '否'}")

print()
print("  [题材标签]")
print(f"  {reason_str}")

# 综合评分
print()
print("=" * 68)
print("  综合评估")
print("=" * 68)

score = 0
checks = []

if c > ma5 > ma10 > ma20:
    score += 25
    checks.append(("均线多头排列", 25))
elif c > ma5 > ma10:
    score += 15
    checks.append(("站上MA5/MA10", 15))
elif c > ma5:
    score += 8
    checks.append(("站上MA5", 8))
else:
    checks.append(("均线偏弱", 0))

if 60 <= rsi14 <= 75:
    score += 20
    checks.append((f"RSI={rsi14:.1f}强势", 20))
elif 55 <= rsi14 < 60:
    score += 12
    checks.append((f"RSI={rsi14:.1f}中性偏强", 12))
elif rsi14 > 80:
    score -= 10
    checks.append(("RSI过热", -10))
else:
    checks.append((f"RSI={rsi14:.1f}偏弱", 0))

if dif > dea > 0:
    score += 20
    checks.append(("MACD多头排列", 20))
elif dif > dea:
    score += 10
    checks.append(("MACD金叉", 10))
else:
    checks.append(("MACD非多头", 0))

if vol_ratio > 1.5:
    score += 15
    checks.append((f"放量{vol_ratio:.1f}x", 15))
elif vol_ratio > 1.2:
    score += 10
    checks.append((f"温和放量{vol_ratio:.1f}x", 10))
elif vol_ratio < 0.8:
    score -= 5
    checks.append(("缩量", -5))
else:
    checks.append((f"量比{vol_ratio:.1f}正常", 0))

if 3 <= dev_20 <= 15:
    score += 15
    checks.append((f"乖离{dev_20:.1f}%适中", 15))
elif dev_20 > 25:
    score -= 8
    checks.append(("乖离过大", -8))
else:
    checks.append((f"乖离{dev_20:.1f}%", 0))

if is_sanyang:
    score += 10
    checks.append(("三连阳", 10))
else:
    checks.append(("非三连阳", 0))

if chg_pct > 0:
    score += 5
    checks.append(("今日收涨", 5))

for chk, pts in checks:
    print(f"  {chk:<24} {pts:+d}")

bar = "#" * int(score / 5) + "-" * (20 - int(score / 5))
print(f"  {'─'*42}")
print(f"  实时评分: {score}/100  [{bar}]")

if score >= 75:
    level = "强势 - 隔日短线条件成立"
elif score >= 55:
    level = "偏强 - 可关注，等待放量确认"
elif score >= 35:
    level = "中性 - 暂不建议入场"
else:
    level = "偏弱 - 回避"
print(f"  结论: {level}")
