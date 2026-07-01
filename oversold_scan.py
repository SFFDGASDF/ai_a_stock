"""超跌反弹扫描 — 今天大跌 明天反弹（安全版）"""
import pandas as pd
import numpy as np
import time
import logging
logging.getLogger("tdxpy").setLevel(logging.CRITICAL)
from mootdx.quotes import Quotes
from stockstats import StockDataFrame
import requests

client = Quotes.factory(market="std")
UA = "Mozilla/5.0"

print("=" * 68)
print("  超跌反弹扫描 — 今天大跌 → 明天反弹")
print("=" * 68)

# ===== 大盘环境检测 =====
print("\n  [0/5] 大盘环境检测...")
up_count = 0
down_count = 0
flat_count = 0
total_count = 0

# 获取沪深股票列表用于大盘检测
stocks_sh = client.stocks(market=1)
stocks_sz = client.stocks(market=0)
df_all = pd.concat([stocks_sh, stocks_sz], ignore_index=True)

sample_codes = []
for _, s in df_all.iterrows():
    code = str(s.get("code", ""))
    name = str(s.get("name", ""))
    if (len(code) == 6 and code[:3] in ("600","601","603","605","000","002","003","300")
        and not name.startswith(("ST","st","*ST"))):
        sample_codes.append(code)

# 抽500只统计涨跌
sample = sample_codes[:500]
for i in range(0, len(sample), 80):
    batch = sample[i:i+80]
    try:
        quotes = client.quotes(symbol=batch)
        if quotes is None or len(quotes) == 0:
            continue
        for _, q in quotes.iterrows():
            price = float(q.get("price", 0) or 0)
            prev = float(q.get("last_close", 0) or 0)
            if price <= 0 or prev <= 0:
                continue
            total_count += 1
            chg = (price / prev - 1) * 100
            if chg > 0.5: up_count += 1
            elif chg < -0.5: down_count += 1
            else: flat_count += 1
    except:
        pass
    time.sleep(0.1)

up_ratio = up_count / total_count * 100 if total_count > 0 else 50
down_ratio = down_count / total_count * 100 if total_count > 0 else 50

market_score = 0
if up_ratio >= 60: market_score = 2; env_label = "🟢 强势"
elif up_ratio >= 50: market_score = 1; env_label = "🟢 偏强"
elif up_ratio >= 40: market_score = 0; env_label = "🟡 震荡"
elif up_ratio >= 30: market_score = -1; env_label = "🟠 偏弱"
else: market_score = -2; env_label = "🔴 弱势"

print(f"    {env_label}  涨:{up_count}({up_ratio:.0f}%)  跌:{down_count}({down_ratio:.0f}%)  平:{flat_count}")

# Step 1: 复用已获取的股票列表
all_codes = []
for _, s in df_all.iterrows():
    code = str(s.get("code", ""))
    name = str(s.get("name", ""))
    if (len(code) == 6
        and not name.startswith(("ST", "st", "*ST", "N", "C"))
        and code[:3] in ("600","601","603","605","000","002","003","300")
        and code[:3] != "301"):
        all_codes.append((code, name))

name_map = dict(all_codes)
codes = [c for c, _ in all_codes]
print(f"    共 {len(codes)} 只")

# Step 2: 批量行情过滤
print("\n  [2/5] 行情扫描 (找今日大跌)...")
candidates = []
batch_size = 80

for i in range(0, len(codes), batch_size):
    batch = codes[i:i+batch_size]
    try:
        quotes = client.quotes(symbol=batch)
        if quotes is None or len(quotes) == 0:
            continue
        for _, q in quotes.iterrows():
            code = str(q.get("code", "")).zfill(6)
            price = float(q.get("price", 0) or 0)
            prev = float(q.get("last_close", 0) or 0)
            open_p = float(q.get("open", 0) or 0)
            high = float(q.get("high", 0) or 0)
            low = float(q.get("low", 0) or 0)
            amount = float(q.get("amount", 0) or 0)

            if price <= 0 or prev <= 0:
                continue

            chg_pct = (price / prev - 1) * 100

            # 今日跌幅 -8% 到 -2%
            if chg_pct > -2 or chg_pct < -8:
                continue
            if amount < 30000000:
                continue
            if price < 3:
                continue

            lower_shadow = (min(price, open_p) - low) / open_p * 100
            amplitude = (high / low - 1) * 100

            candidates.append({
                "code": code, "price": price, "open": open_p,
                "high": high, "low": low, "prev": prev,
                "chg": chg_pct, "amount": amount,
                "lower_shadow": lower_shadow, "amplitude": amplitude,
            })
    except:
        pass

    if (i // batch_size + 1) % 20 == 0:
        print(f"    进度: {min(i+batch_size, len(codes))}/{len(codes)}, 已发现 {len(candidates)} 候选")

print(f"    今日跌2-8%+非ST+>3000万: {len(candidates)} 只")

# 按下影线排序取前80
candidates.sort(key=lambda x: x["lower_shadow"] - abs(x["chg"]) / 10, reverse=True)
candidates = candidates[:80]

# Step 3: 技术面分析
print(f"\n  [3/5] 技术面深度分析 ({len(candidates)} 只)...")
results = []

for idx, c in enumerate(candidates):
    code = c["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 30:
            continue

        df = bars.copy()
        close = df["close"].astype(float)
        vol = df["vol"].astype(float)
        high_s = df["high"].astype(float)
        low_s = df["low"].astype(float)

        cur = close.iloc[-1]

        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else 0

        v_today = float(vol.iloc[-1])
        v_5avg = float(vol.iloc[-5:].mean())
        vr = v_today / v_5avg if v_5avg > 0 else 1

        stock = StockDataFrame.retype(df)
        try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
        except: rsi6 = 50
        try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
        except: rsi14 = 50
        try:
            dif = float(stock["macd"].dropna().iloc[-1])
            dea = float(stock["macds"].dropna().iloc[-1])
            macdh = float(stock["macdh"].dropna().iloc[-1])
        except:
            dif=dea=macdh=0
        try:
            kdj_j = float(stock["kdjj"].dropna().iloc[-1])
        except:
            kdj_j = 50
        try:
            boll_u = float(stock["boll_ub"].dropna().iloc[-1])
            boll_m = float(stock["boll"].dropna().iloc[-1])
            boll_pos = (cur - float(stock["boll_lb"].dropna().iloc[-1])) / (boll_u - float(stock["boll_lb"].dropna().iloc[-1])) * 100
        except:
            boll_pos = 50

        chg_5d = (cur / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0

        # 连阴天数（连续下跌天数）
        down_days = 0
        for d in range(1, min(10, len(close))):
            if float(close.iloc[-d]) < float(close.iloc[-d-1]):
                down_days += 1
            else:
                break

        # 支撑
        nearest_support = "无"
        support_dist = 99
        for label, ma in [("MA20", ma20), ("MA60", ma60)]:
            if ma > 0 and cur > ma:
                d = (cur / ma - 1) * 100
                if d < support_dist:
                    support_dist = d
                    nearest_support = label

        # === 评分（正面 70 + 惩罚）===
        score = 0
        details = []
        penalty = 0
        dev = (cur / ma20 - 1) * 100 if ma20 > 0 else 999
        chg_abs = abs(c["chg"])
        ls = c["lower_shadow"]

        # --- 正面分 ---
        # 1. 超跌 (max 25)
        if 5 <= chg_abs <= 7:
            score += 25; details.append(("跌5-7%黄金坑", 25))
        elif 4 <= chg_abs < 5:
            score += 20; details.append((f"跌{chg_abs:.0f}%", 20))
        elif 7 <= chg_abs < 8:
            score += 18; details.append(("跌7-8%", 18))
        else:
            score += 14; details.append((f"跌{chg_abs:.0f}%", 14))

        # 2. 下影线 (max 20)
        if ls > 3:
            score += 20; details.append((f"长下影{ls:.1f}%", 20))
        elif ls > 1.5:
            score += 14; details.append((f"下影{ls:.1f}%", 14))
        elif ls > 0.5:
            score += 8; details.append((f"短下影{ls:.1f}%", 8))
        else:
            score += 3; details.append(("无下影", 3))

        # 3. 均线支撑 (max 20, 乖离大降级)
        if cur > ma5 > ma10 > ma20 and ma20 > 0:
            if dev <= 12:
                score += 20; details.append(("多头+乖离安全", 20))
            elif dev <= 20:
                score += 12; details.append((f"多头(乖离{dev:.0f}%)", 12))
            else:
                score += 6; details.append((f"多头但乖离{dev:.0f}%", 6))
        elif cur > ma20 and ma20 > cur * 0.93:
            score += 15; details.append(("MA20支撑", 15))
        elif ma60 > 0 and cur > ma60:
            score += 10; details.append(("MA60支撑", 10))
        elif cur > ma5:
            score += 8; details.append(("MA5附近", 8))
        else:
            score += 3; details.append(("破MA5", 3))

        # 4. RSI (max 15)
        if rsi6 < 30:
            score += 15; details.append((f"RSI={rsi6:.0f}超卖", 15))
        elif rsi6 < 40:
            score += 12; details.append((f"RSI={rsi6:.0f}偏低", 12))
        elif rsi6 < 50:
            score += 8; details.append((f"RSI={rsi6:.0f}", 8))
        else:
            score += 5; details.append((f"RSI={rsi6:.0f}", 5))

        # 5. MACD (max 10)
        if dif > dea and dif > 0:
            score += 10; details.append(("MACD多头", 10))
        elif dif > dea:
            score += 7; details.append(("MACD金叉", 7))
        elif dif > dea - 0.05:
            score += 5; details.append(("MACD将金叉", 5))
        else:
            score += 2; details.append(("MACD弱势", 2))

        # 6. 量能 (max 10，缩量=0)
        if 1.2 <= vr <= 2.5:
            score += 10; details.append((f"放量{vr:.1f}x", 10))
        elif 0.8 <= vr <= 1.2:
            score += 6; details.append((f"量{vr:.1f}x", 6))
        elif vr > 2.5:
            score += 4; details.append(("巨量", 4))
        else:
            pass  # 缩量不加分

        # --- 🔑 安全罚分（无上限） ---
        # 高位补跌
        if dev > 30: penalty += 20; details.append((f"崩盘乖离{dev:.0f}%", -20))
        elif dev > 25: penalty += 15; details.append((f"乖离{dev:.0f}%严重", -15))
        elif dev > 18: penalty += 8; details.append((f"乖离{dev:.0f}%偏高", -8))
        # RSI还高=假超跌
        if rsi6 > 65: penalty += 10; details.append((f"RSI{rsi6:.0f}假超跌", -10))
        elif rsi6 > 55: penalty += 4; details.append((f"RSI{rsi6:.0f}未超卖", -4))
        # 无量=没人玩
        if vr < 0.3: penalty += 20; details.append((f"无量{vr:.1f}x-无人交易", -20))
        elif vr < 0.5: penalty += 10; details.append((f"缩量{vr:.1f}x-流动性差", -10))
        elif vr < 0.8: penalty += 3; details.append((f"缩量{vr:.1f}x", -3))
        # 前期涨太多=获利盘砸
        if chg_5d > 15: penalty += 8; details.append((f"5日+{chg_5d:.0f}%追高", -8))
        elif chg_5d > 10: penalty += 5; details.append((f"5日+{chg_5d:.0f}%-获利回吐", -5))
        # 连续下跌=趋势反转
        if chg_5d < -10: penalty += 8; details.append((f"5日{chg_5d:.0f}%连跌", -8))
        # 连阴天数（比5日跌幅更精确）
        if down_days >= 4:
            penalty += 10; details.append((f"连阴{down_days}天", -10))
        elif down_days >= 3:
            penalty += 5; details.append((f"连阴{down_days}天", -5))
        # 高位股
        if cur > 80: penalty += 5; details.append((f"高价{cur:.0f}元", -5))
        # KDJ/振幅
        if kdj_j < -5: penalty += 2
        if c["amplitude"] > 8: penalty += 2

        score -= penalty

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": cur, "chg": c["chg"],
            "lower_shadow": ls, "amplitude": c["amplitude"],
            "amount": c["amount"], "rsi6": rsi6, "rsi14": rsi14,
            "dif": dif, "dea": dea, "macdh": macdh,
            "kdj_j": kdj_j, "vr": vr, "chg_5d": chg_5d,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "support": nearest_support, "support_dist": support_dist,
            "boll_pos": boll_pos, "dev": dev, "score": score, "details": details,
            "down_days": down_days,
        })
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)

# Step 4: 用腾讯补全名字
print("\n  [4/5] 获取股票名称...")
need_names = [r for r in results[:15] if not r["name"]]
if need_names:
    try:
        url = "https://qt.gtimg.cn/q=" + ",".join(
            [f"sz{r['code']}" if r["code"][0] in "023" else f"sh{r['code']}" for r in need_names])
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        text = resp.content.decode("gbk")
        for r in need_names:
            prefix = "sz" if r["code"][0] in "023" else "sh"
            for line in text.split("\n"):
                if f"v_{prefix}{r['code']}" in line:
                    parts = line.split("~")
                    if len(parts) > 1:
                        r["name"] = parts[1]
    except:
        pass

# 输出
print(f"\n{'='*68}")
print(f"  🏆 超跌反弹 TOP15  (大盘: {env_label})")
print(f"{'='*68}")

for i, r in enumerate(results[:15]):
    name_str = r["name"] or f"({r['code']})"
    bar_len = max(0, int(r["score"] / 5))
    bar = "▓" * bar_len + "░" * (20 - bar_len)
    
    # 安全检查
    warnings = []
    if r["vr"] < 0.3: warnings.append("⚠️无量")
    elif r["vr"] < 0.5: warnings.append("⚠️缩量")
    if r["rsi6"] > 65: warnings.append("⚠️假超跌")
    if r.get("dev", 0) > 25: warnings.append("🔴高位崩")
    elif r.get("dev", 0) > 18: warnings.append("⚠️乖离高")
    if r["chg_5d"] > 12: warnings.append("⚠️获利盘")
    if r["chg_5d"] < -10: warnings.append("⚠️连跌")
    if r.get("down_days", 0) >= 4: warnings.append(f"🔴连阴{r['down_days']}天")
    elif r.get("down_days", 0) >= 3: warnings.append(f"⚠️连阴{r['down_days']}天")
    if r["price"] > 80: warnings.append("⚠️高价")
    
    if warnings:
        tag = "🚫险" if r["score"] < 55 else ("🔴危" if any(w.startswith("🔴") for w in warnings) else "⚠️慎")
    else:
        tag = "🟢买" if r["score"] >= 75 else ("🟡观" if r["score"] >= 60 else "⚪等")
    
    warn_str = " ".join(warnings) if warnings else "无风险信号"

    print(f"\n  #{i+1} {name_str}({r['code']})  ¥{r['price']:.2f}  今日{r['chg']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  RSI6={r['rsi6']:.0f}/RSI14={r['rsi14']:.0f}  量比={r['vr']:.1f}x  下影={r['lower_shadow']:.1f}%  振幅={r['amplitude']:.1f}%")
    print(f"  KDJ-J={r['kdj_j']:.0f}  BOLL位置={r['boll_pos']:.0f}%  风险: {warn_str}")
    print(f"  MA5=¥{r['ma5']:.2f}  MA20=¥{r['ma20']:.2f}  MA60=¥{r['ma60']:.2f}  MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f}")

if results:
    # 安全过滤: 量比/RSI/乖离/连跌/连阴
    safe = [r for r in results
            if r["vr"] >= 0.5
            and r["rsi6"] <= 65
            and r.get("dev", 0) <= 25
            and r["chg_5d"] > -10
            and r.get("down_days", 0) < 4]
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]
    
    # 风险检查
    risk_flags = []
    if best["vr"] < 0.3: risk_flags.append("低流动性")
    if best.get("dev", 0) > 25: risk_flags.append("高位崩盘")
    if best["rsi6"] > 65: risk_flags.append("假超跌")
    if best["chg_5d"] < -10: risk_flags.append("连续下跌")
    if best.get("down_days", 0) >= 4: risk_flags.append(f"连阴{best['down_days']}天")
    
    # 大盘门控: 弱市超跌策略风险翻倍
    score_threshold = 72 if market_score >= -1 else 80
    
    print(f"\n{'='*68}")
    print(f"  🎯 最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'='*68}")
    print(f"\n  现价: ¥{best['price']:.2f}    今日跌幅: {best['chg']:.1f}%")
    print(f"  大盘: {env_label}")
    
    if market_score <= -2:
        print(f"\n  🔴 大盘环境极弱（涨{up_ratio:.0f}%跌{down_ratio:.0f}%），超跌策略风险极高")
        print(f"  不建议买入，空仓等待市场企稳")
    elif risk_flags:
        print(f"\n  ⚠️ 风险: {', '.join(risk_flags)} — 不推荐买入")
        print(f"  今日市场不适合超跌策略，建议空仓等待")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 今日尾盘 / 明早低开")
        print(f"  目标: ¥{best['price']*1.04:.2f}(+4%) ~ ¥{best['price']*1.05:.2f}(+5%)")
        print(f"  止损: ¥{best['price']*0.97:.2f}(-3%)")
        print(f"\n  ⚠ 超跌反弹风险高于顺势交易，控制仓位 ≤ 20%")
    elif best["score"] >= 60:
        print(f"\n  ⚠ 评分 {best['score']}/100，勉强可关注但别重仓")
        print(f"  仓位 ≤ 10%，止损 ¥{best['price']*0.97:.2f}(-3%)")
    else:
        print(f"\n  ⚠ 评分不足 {best['score']}/100，不建议买入。等更好的机会。")

print(f"\n  ⚠ 以上为技术分析，不构成投资建议")
