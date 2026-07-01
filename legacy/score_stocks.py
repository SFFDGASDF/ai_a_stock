"""对 10 只强势股做多因子技术评分排名"""
import pandas as pd
import numpy as np
import time
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

STOCKS = [
    ("600516", "方大炭素", "石墨电极龙头+电池材料+核电石墨"),
    ("688268", "华特气体", "电子特气+氦气+光刻气+国产替代"),
    ("002156", "通富微电", "CPO封装+AMD产业链+存储芯片封测"),
    ("600487", "亨通光电", "多芯光纤+CPO+一季报增长"),
    ("301366", "一博科技", "AI PCB+光模块+英伟达合作+签单增长"),
    ("603236", "移远通信", "卫星通信+物联网模组+人形机器人"),
    ("600688", "上海石化", "T1000级高性能碳纤维+石油化工+央企"),
    ("600121", "郑州煤电", "煤炭+机器人+算力中心+郑州国资"),
    ("002965", "祥鑫科技", "液冷服务器+人形机器人+汽车零部件"),
    ("688655", "迅捷兴", "800G光模块+PCB+定增AI服务器"),
]

client = Quotes.factory(market='std')


def calc_indicators(code):
    """计算技术指标"""
    bars = client.bars(symbol=code, category=4, offset=120)
    if bars is None or len(bars) < 30:
        return None
    df = pd.DataFrame(bars)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime').sort_index()
    
    stock = StockDataFrame.retype(df)
    close = df['close']
    
    last = {}
    try:
        last['rsi_14'] = float(stock['rsi_14'].dropna().iloc[-1])
    except:
        last['rsi_14'] = 50
    try:
        last['macd'] = float(stock['macd'].dropna().iloc[-1])
        last['macds'] = float(stock['macds'].dropna().iloc[-1])
    except:
        last['macd'] = last['macds'] = 0
    try:
        last['boll'] = float(stock['boll'].dropna().iloc[-1])
        last['boll_ub'] = float(stock['boll_ub'].dropna().iloc[-1])
        last['boll_lb'] = float(stock['boll_lb'].dropna().iloc[-1])
    except:
        last['boll'] = last['boll_ub'] = last['boll_lb'] = 0
    try:
        last['kdjk'] = float(stock['kdjk'].dropna().iloc[-1])
        last['kdjd'] = float(stock['kdjd'].dropna().iloc[-1])
        last['kdjj'] = float(stock['kdjj'].dropna().iloc[-1])
    except:
        last['kdjk'] = last['kdjd'] = last['kdjj'] = 50
    
    last['close'] = float(close.iloc[-1])
    last['ma5'] = float(close.rolling(5).mean().iloc[-1])
    last['ma10'] = float(close.rolling(10).mean().iloc[-1])
    last['ma20'] = float(close.rolling(20).mean().iloc[-1])
    last['ma60'] = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None
    
    # 区间涨跌幅
    if len(close) >= 5:
        last['chg_5d'] = (close.iloc[-1] / close.iloc[-5] - 1) * 100
    else:
        last['chg_5d'] = 0
    if len(close) >= 20:
        last['chg_20d'] = (close.iloc[-1] / close.iloc[-20] - 1) * 100
    else:
        last['chg_20d'] = 0
    
    # 量比
    vol = df['vol']
    last['vol_ratio'] = float(vol.iloc[-5:].mean() / vol.iloc[-20:].mean()) if len(vol) >= 20 else 1.0
    
    return last


def score_stock(code, name, reason):
    """综合技术评分 0-100"""
    ind = calc_indicators(code)
    if ind is None:
        return None
    
    score = 0
    signals = []
    c = ind['close']
    
    # --- RSI (0-25) ---
    rsi = ind['rsi_14']
    if rsi < 20:
        score += 25
        signals.append("RSI极度超卖→反弹概率高")
    elif rsi < 30:
        score += 20
        signals.append("RSI超卖→关注反弹")
    elif 30 <= rsi <= 70:
        score += 18
    elif rsi > 80:
        score += 5
        signals.append("RSI超买→注意回调")
    elif rsi > 70:
        score += 10
    else:
        score += 13
    
    # --- MACD (0-20) ---
    dif, dea = ind['macd'], ind['macds']
    if dif > dea > 0:
        score += 20
        signals.append("MACD多头✓")
    elif dif > dea:
        score += 12
    elif dif < dea < 0:
        score += 3
        signals.append("MACD空头")
    else:
        score += 7
    
    # --- 均线排列 (0-25) ---
    ma5, ma10, ma20, ma60 = ind['ma5'], ind['ma10'], ind['ma20'], ind['ma60']
    if ma60 and c > ma5 > ma10 > ma20 > ma60:
        score += 25
        signals.append("完美多头排列✓")
    elif c > ma5 > ma10 > ma20:
        score += 20
        signals.append("均线多头✓")
    elif c > ma20:
        score += 12
    elif c < ma5 < ma10 < ma20:
        score += 3
        signals.append("均线空头")
    else:
        score += 8
    
    # --- 量价配合 (0-15) ---
    vol_ratio = ind['vol_ratio']
    chg_5d = ind['chg_5d']
    if chg_5d > 0 and vol_ratio > 1.3:
        score += 15
        signals.append("放量上涨→资金关注")
    elif chg_5d > 0 and vol_ratio > 1.0:
        score += 10
    elif chg_5d < 0 and vol_ratio < 0.7:
        score += 10
        signals.append("缩量回调→洗盘特征")
    elif chg_5d > 3 and vol_ratio < 0.8:
        score += 3
        signals.append("价涨量缩→背离风险")
    else:
        score += 6
    
    # --- KDJ (0-15) ---
    k, d_val, j = ind['kdjk'], ind['kdjd'], ind['kdjj']
    if j < 0:
        score += 15
        signals.append("KDJ J<0→超卖底部")
    elif k > d_val and 20 < k < 80:
        score += 12
    elif j > 100:
        score += 3
        signals.append("KDJ超买")
    else:
        score += 7
    
    # 评级
    if score >= 80:
        level = "🟢 强烈推荐"
    elif score >= 65:
        level = "🟢 推荐"
    elif score >= 50:
        level = "🟡 关注"
    elif score >= 35:
        level = "⚪ 观望"
    else:
        level = "🔴 回避"
    
    return {
        'code': code, 'name': name, 'reason': reason,
        'score': score, 'level': level, 'signals': signals,
        'rsi': round(rsi, 1), 'chg_5d': round(chg_5d, 1),
        'vol_ratio': round(vol_ratio, 2),
        'price': round(c, 2), 'ma20': round(ma20, 2),
    }


# === 主流程 ===
print("=" * 70)
print("  10只强势股 · 多因子技术评分排名")
print("  维度: RSI(25) + MACD(20) + 均线(25) + 量价(15) + KDJ(15)")
print("=" * 70)

results = []
for code, name, reason in STOCKS:
    print(f"  分析 {code} {name} ...")
    try:
        r = score_stock(code, name, reason)
        if r:
            results.append(r)
            bar = '█' * (r['score'] // 5) + '░' * (20 - r['score'] // 5)
            print(f"    [{bar}] {r['score']}/100 → {r['level']}")
        time.sleep(0.3)
    except Exception as e:
        print(f"    ✗ 失败: {e}")

results.sort(key=lambda x: x['score'], reverse=True)

print(f"\n{'='*70}")
print(f"  最终排名")
print(f"{'='*70}")
print(f"{'排名':<5}{'代码':<10}{'名称':<10}{'评分':<6}{'建议':<14}{'RSI':<7}{'5日%':<8}{'量比':<7}{'现价':<8}")
print(f"{'-'*70}")

for i, r in enumerate(results):
    print(f"{i+1:<5}{r['code']:<10}{r['name']:<10}{r['score']:<6}{r['level']:<14}"
          f"{r['rsi']:<7}{r['chg_5d']:<8}{r['vol_ratio']:<7}{r['price']:<8}")

print(f"\n{'='*70}")
print(f"  推荐详情")
print(f"{'='*70}")

for i, r in enumerate(results[:3]):
    print(f"\n  🏆 TOP{i+1}: {r['name']}({r['code']}) — {r['score']}分 {r['level']}")
    print(f"  题材: {r['reason']}")
    print(f"  现价: {r['price']} | 5日涨跌: {r['chg_5d']:+.1f}% | RSI: {r['rsi']} | 量比: {r['vol_ratio']}")
    print(f"  MA20: {r['ma20']}")
    print(f"  信号: {'; '.join(r['signals'])}")
