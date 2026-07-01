"""吴通控股 300292 实时分析"""
import logging, sys
logging.getLogger('tdxpy').setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

CODE = '300292'
c = Quotes.factory(market='std', timeout=10)
bars = c.bars(symbol=CODE, category=4, offset=120)
df = bars[-120:].copy()
sdf = StockDataFrame.retype(df)

cur = float(c.quotes(symbol=CODE).iloc[0]['price'])
prev = float(c.quotes(symbol=CODE).iloc[0]['last_close'])
chg = (cur/prev-1)*100
open_p = float(c.quotes(symbol=CODE).iloc[0]['open'])
high = float(c.quotes(symbol=CODE).iloc[0]['high'])
low = float(c.quotes(symbol=CODE).iloc[0]['low'])
amount = float(c.quotes(symbol=CODE).iloc[0]['amount'])
vol = float(c.quotes(symbol=CODE).iloc[0]['vol'])

ma5 = float(sdf['close_5_sma'].iloc[-1])
ma10 = float(sdf['close_10_sma'].iloc[-1])
ma20 = float(sdf['close_20_sma'].iloc[-1])
ma60 = float(sdf['close_60_sma'].iloc[-1])
rsi6 = float(sdf['rsi_6'].iloc[-1])
rsi14 = float(sdf['rsi_14'].iloc[-1])
macd_dif = float(sdf['macd'].iloc[-1])
macd_dea = float(sdf['macds'].iloc[-1])
macd_bar = float(sdf['macdh'].iloc[-1])
kdj_j = float(sdf['kdjj'].iloc[-1])
boll_mid = float(sdf['boll'].iloc[-1])

chg_1d = (df['close'].iloc[-1]/df['close'].iloc[-2]-1)*100
chg_3d = (df['close'].iloc[-1]/df['close'].iloc[-4]-1)*100
chg_5d = (df['close'].iloc[-1]/df['close'].iloc[-6]-1)*100
avg_vol_5 = float(df['vol'].iloc[-6:-1].mean())
vr = float(df['vol'].iloc[-1])/avg_vol_5 if avg_vol_5 > 0 else 0
dev = (cur - ma5)/ma5*100
lower_shadow = (min(open_p, cur) - low)/low*100 if low > 0 else 0
amplitude = (high - low)/low*100 if low > 0 else 0

ma120_high = float(df['close'].iloc[-120:].max())
ma120_low = float(df['close'].iloc[-120:].min())

# 均线排列
ma_order = ""
if ma5 > ma10 > ma20 > ma60:
    ma_order = "🔴 完美多头"
elif ma5 > ma10 > ma20:
    ma_order = "🟡 多头(缺60)"
elif ma5 < ma10 < ma20:
    ma_order = "🟢 空头排列"
elif cur < ma5:
    ma_order = "⚠️ 跌破MA5"

print(f'===============================================')
print(f'  吴通控股(300292)')
print(f'===============================================')
print(f'  现价: ¥{cur:.2f}    今开: ¥{open_p:.2f}    最高: ¥{high:.2f}    最低: ¥{low:.2f}')
print(f'  今日: {chg:+.2f}%    昨收: ¥{prev:.2f}')
print(f'  振幅: {amplitude:.1f}%    下影: {lower_shadow:.1f}%    乖离MA5: {dev:+.1f}%')
print(f'  量比: {vr:.1f}x    成交: {amount/1e6:.0f}万    换手: {vol/100:.1f}%')
print(f'')
print(f'  RSI6: {rsi6:.0f}  RSI14: {rsi14:.0f}  KDJ-J: {kdj_j:.0f}  MACD柱: {macd_bar:+.3f}')
print(f'  MACD: DIF={macd_dif:.3f} DEA={macd_dea:.3f}')
print(f'  MA5=¥{ma5:.2f}  MA10=¥{ma10:.2f}  MA20=¥{ma20:.2f}  MA60=¥{ma60:.2f}')
print(f'  BOLL中轨: ¥{boll_mid:.2f}')
print(f'  均线: {ma_order}')
print(f'  120日: 最高¥{ma120_high:.2f}  最低¥{ma120_low:.2f}')
print(f'')
print(f'  近5日:')
for i in range(5, 0, -1):
    d = df.index[-i].strftime('%m/%d') if hasattr(df.index[-i], 'strftime') else str(df.index[-i])[:10]
    close_i = float(df['close'].iloc[-i])
    chg_i = (close_i / float(df['close'].iloc[-i-1]) - 1) * 100
    vol_i = float(df['vol'].iloc[-i])
    print(f'    {d}  ¥{close_i:.2f}  {chg_i:+.1f}%  {vol_i/1e4:.0f}万手')

print(f'')
print(f'  目标: ¥{cur*1.04:.2f}(+4%) ~ ¥{cur*1.05:.2f}(+5%)')
print(f'  止损: ¥{cur*0.97:.2f}(-3%)')
