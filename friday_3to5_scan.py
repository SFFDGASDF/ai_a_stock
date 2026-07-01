"""周五买→周一卖 3-5%策略 — 全市场涨幅3-7%扫 + 技术面精选"""
import pandas as pd
import numpy as np
import requests
import time
import json
from mootdx.quotes import Quotes
from stockstats import StockDataFrame

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"
client = Quotes.factory(market="std")

print("=" * 72)
print("  周五买→周一卖  3-5%稳健策略  全市场扫描")
print("=" * 72)

# ===== Step 1: 从东财拉今日涨幅3-7%的活跃股 =====
print("\n  [1/4] 东财全市场涨幅榜...")

candidates = []

# 东财行情中心 - 按涨幅排序取前300
for page in range(1, 5):
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": page,
            "pz": 80,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",  # 按涨跌幅排序
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",  # 沪深A股
            "fields": "f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f20,f21",
        }
        r = requests.get(url, params=params, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=15)
        data = r.json()
        items = data.get("data", {}).get("diff", [])
        if not items:
            break
        
        for item in items:
            code = str(item.get("f12", "")).zfill(6)
            name = str(item.get("f14", ""))
            price = item.get("f2", 0)
            chg_pct = item.get("f3", 0)
            volume = item.get("f5", 0)  # 成交量(手)
            amount = item.get("f6", 0)  # 成交额
            turnover = item.get("f8", 0)  # 换手率
            high = item.get("f15", 0)
            low = item.get("f16", 0)
            prev_close = item.get("f18", 0)
            
            if not code or not price or price == "-":
                continue
            
            price = float(price) if isinstance(price, (int, float)) else float(price)
            chg_pct = float(chg_pct) if isinstance(chg_pct, (int, float)) else float(chg_pct)
            turnover = float(turnover) if isinstance(turnover, (int, float)) and turnover != "-" else 0
            amount = float(amount) if isinstance(amount, (int, float)) and amount != "-" else 0
            
            # 判断涨停板
            is_20cm = code.startswith("30") or code.startswith("68")
            limit_pct = 20 if is_20cm else 10
            is_limit_up = chg_pct >= (limit_pct - 0.5)
            
            # 过滤条件: 涨幅3-7%, 非涨停, 非ST(名称不含ST), 成交额>5000万
            is_st = "ST" in name or "*ST" in name
            
            if (3 <= chg_pct <= 7 
                and not is_limit_up 
                and not is_st
                and amount > 50000000  # 5000万以上
                and turnover >= 1):    # 换手率>=1%
                
                candidates.append({
                    "code": code, "name": name, "price": price,
                    "chg_pct": chg_pct, "turnover": turnover,
                    "amount": amount, "prev_close": prev_close,
                })
        time.sleep(0.5)
    except Exception as e:
        print(f"    Page {page} 失败: {e}")
        break

# 去重
seen = set()
uniq = []
for c in candidates:
    if c["code"] not in seen:
        seen.add(c["code"])
        uniq.append(c)
candidates = uniq

print(f"  涨幅3-7% + 非ST + 成交额>5000万 + 换手>1%: {len(candidates)} 只")

if len(candidates) == 0:
    print("  ❌ 无候选，放宽条件...")
    # 放宽到2-8%
    for page in range(1, 5):
        try:
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": page, "pz": 80, "po": 1, "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2, "invt": 2, "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": "f2,f3,f5,f6,f8,f12,f14,f15,f16,f18",
            }
            r = requests.get(url, params=params, headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}, timeout=15)
            items = r.json().get("data", {}).get("diff", [])
            if not items: break
            for item in items:
                code = str(item.get("f12", "")).zfill(6)
                name = str(item.get("f14", ""))
                price = item.get("f2", 0)
                chg_pct = item.get("f3", 0)
                amount = item.get("f6", 0)
                turnover = item.get("f8", 0)
                if not code or not price or price == "-": continue
                price = float(price)
                chg_pct = float(chg_pct)
                turnover = float(turnover) if turnover and turnover != "-" else 0
                amount = float(amount) if amount and amount != "-" else 0
                is_st = "ST" in str(name)
                is_20cm = code.startswith("30") or code.startswith("68")
                limit_pct = 20 if is_20cm else 10
                is_limit_up = chg_pct >= (limit_pct - 0.5)
                if 2 <= chg_pct <= 8 and not is_limit_up and not is_st and amount > 30000000 and turnover >= 0.5:
                    candidates.append({
                        "code": code, "name": name, "price": price,
                        "chg_pct": chg_pct, "turnover": turnover,
                        "amount": amount, "prev_close": float(item.get("f18", 0)),
                    })
            time.sleep(0.5)
        except: break
    seen2 = set()
    uniq2 = []
    for c in candidates:
        if c["code"] not in seen2:
            seen2.add(c["code"])
            uniq2.append(c)
    candidates = uniq2
    print(f"  放宽后: {len(candidates)} 只")

if len(candidates) == 0:
    print("  ❌ 仍然没有候选")
    exit()

# 限制数量，按成交额排序取前60
candidates.sort(key=lambda x: x["amount"], reverse=True)
if len(candidates) > 60:
    candidates = candidates[:60]

print(f"  精选候选: {len(candidates)} 只")

# ===== Step 2: 技术面深度分析 =====
print(f"\n  [2/4] mootdx逐只技术分析...")

results = []
for idx, cand in enumerate(candidates):
    code = cand["code"]
    name = cand["name"]
    chg_today = cand["chg_pct"]
    
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
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
        ma60 = float(close.rolling(60).mean().iloc[-1])
        
        v5 = float(vol.iloc[-5:].mean())
        v20 = float(vol.iloc[-20:].mean())
        vol_ratio = v5 / v20 if v20 > 0 else 1
        
        chg_3d = (c / float(close.iloc[-3]) - 1) * 100
        chg_5d = (c / float(close.iloc[-5]) - 1) * 100
        dev = (c / ma20 - 1) * 100
        
        try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
        except: rsi14 = 50
        try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
        except: rsi6 = rsi14
        try:
            dif = float(stock["macd"].dropna().iloc[-1])
            dea = float(stock["macds"].dropna().iloc[-1])
            macdh = float(stock["macdh"].dropna().iloc[-1])
            macdh_prev = float(stock["macdh"].dropna().iloc[-2])
        except: dif=dea=macdh=macdh_prev=0
        try:
            k = float(stock["kdjk"].dropna().iloc[-1])
            j = float(stock["kdjj"].dropna().iloc[-1])
        except: k=j=50
        
        # 振幅
        o_today = float(df["open"].iloc[-1])
        h_today = float(df["high"].iloc[-1])
        l_today = float(df["low"].iloc[-1])
        amplitude = (h_today / l_today - 1) * 100
        upper_shadow = max(0, (h_today - max(c, o_today)) / o_today * 100)
        
        # === 3-5%策略专属评分 ===
        score = 0
        signals = []
        risks = []
        
        # 均线健康度 (20)
        if c > ma5 > ma10 > ma20 and ma60 and ma20 > ma60:
            score += 20; signals.append("均线完美多头")
        elif c > ma5 > ma10 > ma20:
            score += 17; signals.append("短期多头排列")
        elif c > ma5 > ma10:
            score += 12; signals.append("站上MA5/MA10")
        elif c > ma5:
            score += 7
        else:
            risks.append("低于MA5")
        
        # RSI健康 (20) - 3-5%策略更保守
        if 52 <= rsi14 <= 65:
            score += 20; signals.append(f"RSI{rsi14:.0f}健康")
        elif 45 <= rsi14 < 52:
            score += 15
        elif 65 < rsi14 <= 72:
            score += 12
        elif rsi14 > 72:
            score += 5; risks.append(f"RSI{rsi14:.0f}偏高")
        elif rsi14 < 45:
            score += 5; risks.append(f"RSI{rsi14:.0f}偏弱")
        
        # MACD动量 (15)
        if dif > dea > 0 and macdh > macdh_prev:
            score += 15; signals.append("MACD多头加速")
        elif dif > dea > 0:
            score += 12; signals.append("MACD多头")
        elif dif > dea and dif > 0:
            score += 8
        elif dif > dea:
            score += 5
        elif dif > 0:
            score += 3
        
        # 量能 (15) - 温和放量为佳
        if 1.1 <= vol_ratio <= 2.0:
            score += 15; signals.append(f"量比{vol_ratio:.1f}x适中")
        elif vol_ratio > 2.0:
            score += 10; signals.append("明显放量")
        elif 0.8 <= vol_ratio < 1.1:
            score += 8
        else:
            score += 3; risks.append(f"量比{vol_ratio:.1f}x偏低")
        
        # 乖离率 (10) - 3-5%需要空间
        if 2 <= dev <= 12:
            score += 10
        elif -2 <= dev < 2:
            score += 7
        elif 12 < dev <= 18:
            score += 6
        elif dev > 20:
            score += 2; risks.append(f"乖离{dev:.0f}%偏大")
        elif dev < -2:
            score += 4; risks.append("低于MA20")
        
        # 近期强度 (10) - 不能涨太多
        if 0 <= chg_3d <= 10:
            score += 10
        elif 10 < chg_3d <= 15:
            score += 7
        elif chg_3d < 0:
            score += 3
        else:
            score += 4; risks.append("3日涨幅过大")
        
        # 今日涨幅适中分 (5)
        if 3 <= chg_today <= 5:
            score += 5
        elif 5 < chg_today <= 7:
            score += 3
        
        # 上影线扣分
        if upper_shadow > 3:
            score -= min(5, int(upper_shadow))
            risks.append(f"上影线{upper_shadow:.1f}%")
        
        # KDJ超买扣分
        if j > 100:
            score -= 3; risks.append(f"KDJ-J={j:.0f}超买")
        
        score = max(0, min(100, score))
        
        results.append({
            "code": code, "name": name, "price": cand["price"],
            "chg_today": chg_today, "turnover": cand["turnover"],
            "amount": cand["amount"],
            "rsi14": rsi14, "rsi6": rsi6,
            "vol_ratio": vol_ratio,
            "chg_3d": chg_3d, "chg_5d": chg_5d,
            "dev": dev, "amplitude": amplitude,
            "score": score, "signals": signals, "risks": risks,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "dif": dif, "dea": dea, "macdh": macdh,
            "k": k, "j": j, "upper_shadow": upper_shadow,
        })
        time.sleep(0.35)
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)
print(f"  技术分析完成: {len(results)} 只")

# ===== Step 3: 输出 =====
print(f"\n{'='*72}")
print(f"  🏆 3-5%稳健策略 TOP10")
print(f"{'='*72}")

header = f"  {'排名':<4}{'代码':<10}{'名称':<10}{'现价':<8}{'涨%':<6}{'RSI':<6}{'量比':<6}{'乖离':<6}{'评分':<5}{'换手%':<7}"
print(header)
print(f"  {'─'*68}")

for rank, r in enumerate(results[:10]):
    bar = "▓" * int(r["score"] / 5) + "░" * (20 - int(r["score"] / 5))
    print(f"  {rank+1:<4}{r['code']:<10}{r['name']:<10}{r['price']:<8.2f}{r['chg_today']:<6.1f}"
          f"{r['rsi14']:<6.1f}{r['vol_ratio']:<6.2f}{r['dev']:<6.1f}{r['score']:<5}[{bar}]")
    sig_str = " | ".join(r['signals'][:3])
    risk_str = " | ".join(r['risks'][:3])
    print(f"    ✅ {sig_str}")
    if risk_str:
        print(f"    ⚠ {risk_str}")
    print(f"    MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f} KDJ-J={r['j']:.1f} 换手={r['turnover']:.1f}%")

# ===== Step 4: 最终推荐 =====
if len(results) < 3:
    print("\n  ❌ 候选不足")
    exit()

print(f"\n{'='*72}")
print(f"  🎯 周五买→周一卖 3-5% · 最终推荐")
print(f"{'='*72}")

best = results[0]

print(f"""
  首选: {best['name']} ({best['code']})
  现价: ¥{best['price']:.2f}    今日: {best['chg_today']:+.1f}%    评分: {best['score']}/100
  换手率: {best['turnover']:.1f}%

  信号: {'; '.join(best['signals'])}
  {'风险: ' + '; '.join(best['risks']) if best['risks'] else '风险: 无明显风险点'}

  技术面:
    RSI(14)={best['rsi14']:.1f}  RSI(6)={best['rsi6']:.1f}
    MACD: DIF={best['dif']:.3f}  DEA={best['dea']:.3f}  柱={best['macdh']:.3f}
    KDJ: K={best['k']:.1f}  J={best['j']:.1f}
    均线: MA5=¥{best['ma5']:.2f}  MA10=¥{best['ma10']:.2f}  MA20=¥{best['ma20']:.2f}  MA60=¥{best['ma60']:.2f}
    量比: {best['vol_ratio']:.2f}x  乖离(MA20): {best['dev']:.1f}%
    3日涨幅: {best['chg_3d']:+.1f}%  5日涨幅: {best['chg_5d']:+.1f}%

  买入: 今日尾盘直接买入 / 周一开盘竞价
  目标: ¥{best['price']*1.04:.2f}(+4%) ~ ¥{best['price']*1.05:.2f}(+5%)
  止损: ¥{best['price']*0.98:.2f}(-2%)
  卖出: 周一盘中达标即出
  仓位: ≤ 总资金 25%
""")

if len(results) >= 2:
    for i in range(1, min(4, len(results))):
        r = results[i]
        print(f"  备选{i}: {r['name']}({r['code']})  ¥{r['price']:.2f}  今日{r['chg_today']:+.1f}%  评分{r['score']}")
        print(f"         {'; '.join(r['signals'][:2])}")

print(f"""
  ⚠ 3-5%策略比5-10%胜率更高，但周末持仓仍有外盘/政策风险
  ⚠ 以上为技术面分析，不构成投资建议
""")
