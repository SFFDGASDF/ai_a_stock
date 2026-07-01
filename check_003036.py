"""泰坦股份 003036 实时分析"""
import pandas as pd, numpy as np, logging, requests
logging.getLogger("tdxpy").setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

c = Quotes.factory(market="std")
UA = "Mozilla/5.0"
CODE = "003036"

bars = c.bars(symbol=CODE, category=4, offset=120)
df = bars.copy()
close = df["close"].astype(float)
vol = df["vol"].astype(float)

cur = close.iloc[-1]
prev = close.iloc[-2]
o = float(df["open"].iloc[-1])
h = float(df["high"].iloc[-1])
l = float(df["low"].iloc[-1])

ma5 = close.rolling(5).mean().iloc[-1]
ma10 = close.rolling(10).mean().iloc[-1]
ma20 = close.rolling(20).mean().iloc[-1]
ma60 = close.rolling(60).mean().iloc[-1]

chg_today = (cur/prev-1)*100
lower_shadow = (min(cur,o)-l)/o*100
upper_shadow = (h-max(cur,o))/o*100

vr = float(vol.iloc[-1]) / float(vol.iloc[-5:].mean())
dev = (cur/ma20-1)*100

stock = StockDataFrame.retype(df)
try: rsi6=float(stock["rsi_6"].dropna().iloc[-1]); rsi14=float(stock["rsi_14"].dropna().iloc[-1])
except: rsi6=rsi14=50
try:
    dif=float(stock["macd"].dropna().iloc[-1]); dea=float(stock["macds"].dropna().iloc[-1])
    macdh=float(stock["macdh"].dropna().iloc[-1])
except: dif=dea=macdh=0
try: kdj_j=float(stock["kdjj"].dropna().iloc[-1])
except: kdj_j=50
try:
    bu=float(stock["boll_ub"].dropna().iloc[-1]); bm=float(stock["boll"].dropna().iloc[-1])
    bl=float(stock["boll_lb"].dropna().iloc[-1]); bp=(cur-bl)/(bu-bl)*100
except: bu=bm=bl=bp=0

chg_5d=(cur/close.iloc[-6]-1)*100 if len(close)>=6 else 0

print("="*60)
print(f"  泰坦股份(003036) 实时分析")
print("="*60)
print(f"\n  现价: ¥{cur:.2f}  今日: {chg_today:+.2f}%")
print(f"  今开: ¥{o:.2f}  最高: ¥{h:.2f}  最低: ¥{l:.2f}")
print(f"  上影: {upper_shadow:.1f}%  下影: {lower_shadow:.1f}%")
print(f"\n  MA5: ¥{ma5:.2f}  MA10: ¥{ma10:.2f}  MA20: ¥{ma20:.2f}  MA60: ¥{ma60:.2f}")
print(f"  乖离: {dev:.1f}%")
print(f"  RSI6: {rsi6:.0f}  RSI14: {rsi14:.0f}  KDJ-J: {kdj_j:.0f}  量比: {vr:.1f}x")
print(f"  MACD: DIF={dif:.3f} DEA={dea:.3f} 柱={macdh:.3f}")
print(f"  BOLL: 上={bu:.2f} 中={bm:.2f} 下={bl:.2f}  位置={bp:.0f}%")
print(f"  5日: {chg_5d:+.1f}%")

# 评分
score=0
if chg_today <= -5: score+=25
elif chg_today <= -4: score+=20
else: score+=15
if lower_shadow > 3: score+=20
elif lower_shadow > 1.5: score+=14
else: score+=8
if cur > ma5 > ma10 > ma20: score+=20
elif cur > ma20: score+=15
else: score+=8
if rsi6 < 40: score+=15
elif rsi6 < 60: score+=10
else: score+=4
if dif > dea: score+=10
else: score+=4
if 0.8 <= vr <= 2: score+=10
else: score+=5

# 扣分
p=0
if dev > 20: p+=5
if upper_shadow > 3: p+=3
score-=p

print(f"\n  评分: {score}/100")
price_min = cur*0.97
price_max = cur*1.05

print(f"\n  止损: ¥{price_min:.2f}(-3%)   目标: ¥{cur*1.04:.2f}(+4%)")
print(f"  明天不反弹就出。仓位 ≤ 20%。")
