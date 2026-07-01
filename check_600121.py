"""郑州煤电 600121 实时分析"""
import pandas as pd, numpy as np, logging, requests
logging.getLogger("tdxpy").setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

c = Quotes.factory(market="std")
CODE = "600121"

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

chg_today = (cur/prev-1)*100
vr = float(vol.iloc[-1]) / float(vol.iloc[-5:].mean())

stock = StockDataFrame.retype(df)
try: rsi6=float(stock["rsi_6"].dropna().iloc[-1]); rsi14=float(stock["rsi_14"].dropna().iloc[-1])
except: rsi6=rsi14=50
try:
    dif=float(stock["macd"].dropna().iloc[-1]); dea=float(stock["macds"].dropna().iloc[-1])
    macdh=float(stock["macdh"].dropna().iloc[-1])
except: dif=dea=macdh=0
try: kdj_j=float(stock["kdjj"].dropna().iloc[-1])
except: kdj_j=50

cost = 4.92
profit = (cur/cost-1)*100

print("="*55)
print(f"  郑州煤电(600121)")
print("="*55)
print(f"  成本: ¥{cost:.2f}   现价: ¥{cur:.2f}   盈亏: {profit:+.2f}%")
print(f"  今开: ¥{o:.2f}  最高: ¥{h:.2f}  最低: ¥{l:.2f}")
print(f"  今日: {chg_today:+.2f}%")
print(f"  RSI: {rsi6:.0f}/{rsi14:.0f}  KDJ-J: {kdj_j:.0f}  量比: {vr:.1f}x")
print(f"  MACD: DIF={dif:.3f} DEA={dea:.3f} 柱={macdh:.3f}")
print(f"  MA5: ¥{ma5:.2f}  MA10: ¥{ma10:.2f}  MA20: ¥{ma20:.2f}")
print(f"\n  目标: ¥{cost*1.04:.2f}(+4%) ~ ¥{cost*1.05:.2f}(+5%)")
print(f"  止损: ¥{cost*0.97:.2f}(-3%)")
print(f"\n  明天达标就卖。仓位 ≤ 15%。")
