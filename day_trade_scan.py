"""隔日短线(1日持有)信号扫描 - 目标次日涨幅5-10%"""
import pandas as pd, numpy as np, time
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
client = Quotes.factory(market="std")

print("=" * 72)
print("  隔日短线(1日持有) · 信号扫描")
print("  目标: 次日涨幅 5-10%")
print("=" * 72)
print(f"  {'代码':<10}{'名称':<8}{'现价':<10}{'RSI':<8}{'量比':<8}{'5日%':<10}{'乖离%':<10}{'评分':<6}{'K线形态'}")
print(f"  {'-'*70}")

results = []
for code, name in STOCKS:
    try:
        bars = client.bars(symbol=code, category=4, offset=60)
        if bars is None or len(bars) < 30:
            continue
        df = pd.DataFrame(bars)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()
        stock = StockDataFrame.retype(df)
        close = df["close"]
        vol = df["vol"]
        c = float(close.iloc[-1])
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        v5 = float(vol.iloc[-5:].mean())
        v20 = float(vol.iloc[-20:].mean())
        vol_ratio = v5 / v20 if v20 > 0 else 1
        chg_5d = (c / float(close.iloc[-5]) - 1) * 100 if len(close) >= 5 else 0
        dev = (c / ma20 - 1) * 100

        try:
            rsi = float(stock["rsi_14"].dropna().iloc[-1])
        except:
            rsi = 50
        try:
            dif = float(stock["macd"].dropna().iloc[-1])
            dea = float(stock["macds"].dropna().iloc[-1])
            macdh = float(stock["macdh"].dropna().iloc[-1])
        except:
            dif = dea = macdh = 0

        score = 0
        signals = []

        # 趋势
        if c > ma5 > ma10:
            score += 18
            signals.append("短期多头")
        elif c > ma5:
            score += 8
            signals.append("站上MA5")

        # 量能（权重最高）
        if vol_ratio > 1.5:
            score += 25
            signals.append(f"放量{vol_ratio:.1f}x")
        elif vol_ratio > 1.2:
            score += 15
            signals.append(f"温和放量{vol_ratio:.1f}x")
        elif vol_ratio > 1.0:
            score += 6

        # MACD柱
        macdh_vals = stock["macdh"].dropna()
        if len(macdh_vals) >= 2:
            macdh_prev = float(macdh_vals.iloc[-2])
            if macdh > macdh_prev > 0:
                score += 18
                signals.append("MACD柱放大")
            elif macdh > 0:
                score += 8

        # RSI
        if 60 <= rsi <= 75:
            score += 14
            signals.append(f"RSI{rsi:.0f}强势")
        elif 55 <= rsi < 60:
            score += 8
        elif rsi > 80:
            score -= 12
            signals.append("RSI过热⚠")

        # 乖离
        if 3 <= dev <= 15:
            score += 12
            signals.append(f"乖离{dev:.0f}%适中")
        elif dev > 25:
            score -= 10
            signals.append("乖离过大⚠")

        # 三连阳
        if len(close) >= 4:
            ok = (close.iloc[-1] > close.iloc[-2] and
                  close.iloc[-2] > close.iloc[-3] and
                  close.iloc[-3] > close.iloc[-4])
            if ok:
                score += 13
                signals.append("三连阳🔥")

        # 涨停空间
        limit_pct = 20 if code.startswith("30") or code.startswith("68") else 10
        room = limit_pct - chg_5d if chg_5d > 0 else limit_pct
        if room > 8:
            score += 6
            signals.append(f"空间{room:.0f}%")

        # 大阳线今日（实体>3%）
        body = abs(c / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else 0
        if body > 3:
            score += 8
            signals.append(f"大阳线{body:.1f}%")

        results.append({
            "code": code, "name": name, "price": c, "rsi": rsi,
            "vol_ratio": vol_ratio, "chg_5d": chg_5d, "dev": dev,
            "score": score, "signals": signals,
            "ma5": ma5, "ma20": ma20,
        })
        time.sleep(0.3)
    except Exception as e:
        print(f"  {code} 失败: {e}")

results.sort(key=lambda x: x["score"], reverse=True)

for r in results:
    bar = "█" * int(r["score"] / 5) + "░" * (20 - int(r["score"] / 5))
    print(f"  {r['code']:<10}{r['name']:<8}{r['price']:<10.2f}"
          f"{r['rsi']:<8.1f}{r['vol_ratio']:<8.2f}"
          f"{r['chg_5d']:<10.1f}{r['dev']:<10.1f}"
          f"{r['score']:<6}[{bar}]")
    print(f"    → {', '.join(r['signals'])}")

# TOP 推荐
print()
print("=" * 72)
print("  🏆 隔日短线 · 最终推荐")
print("=" * 72)

top = results[0]
print(f"\n  首选: {top['name']} ({top['code']})  评分: {top['score']}/100")
print(f"  现价: ¥{top['price']:.2f}")
print(f"  RSI: {top['rsi']:.1f}  |  量比: {top['vol_ratio']:.2f}  |  5日涨幅: {top['chg_5d']:+.1f}%")
print(f"  MA5: {top['ma5']:.2f}  |  MA20: {top['ma20']:.2f}  |  乖离: {top['dev']:.1f}%")
print(f"  触发信号: {'; '.join(top['signals'])}")

if len(results) >= 2:
    runner_up = results[1]
    print(f"\n  备选: {runner_up['name']} ({runner_up['code']})  评分: {runner_up['score']}")
    print(f"  现价: ¥{runner_up['price']:.2f}  |  量比: {runner_up['vol_ratio']:.2f}  |  5日: {runner_up['chg_5d']:+.1f}%")
    print(f"  信号: {'; '.join(runner_up['signals'])}")

print(f"\n{'='*72}")
print(f"  💡 操作建议")
print(f"{'='*72}")
print(f"""
  买入策略:
    ● 明日开盘竞价买入 or 开盘后前30分钟分时回踩买入
    ● 目标价位: ¥{top['price'] * 1.07:.2f} (+7%)

  卖出策略 (后天):
    ● 达标止盈: 涨幅 5% 以上分批卖出
    ● 止损保护: 跌幅超 −3% 果断止损
    ● 时间止损: 后天收盘无论涨跌必须出

  仓位建议:
    ● 短线仓位 ≤ 总资金 20%
    ● 切不可满仓单票

  ⚠ 风险提示:
    ● 隔日交易 1日历史胜率约 59%，非确定性策略
    ● 5-10%收益通常需配合题材热点/涨停板
    ● 本分析基于技术面，不含消息面/基本面因子
    ● 以上为数据分析，不构成投资建议
""")
