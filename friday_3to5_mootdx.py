"""动量策略 T+1 — 安全版（全市场扫描+风险过滤+安全门）"""
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

print("=" * 72)
print("  📈 动量策略 T+1 — 今日买入 → 明日卖出")
print("=" * 72)

# ===== Step 1: 获取股票列表 =====
print("\n  [1/5] 获取沪深A股列表...")
stocks_sh = client.stocks(market=1)
stocks_sz = client.stocks(market=0)
df_all = pd.concat([stocks_sh, stocks_sz], ignore_index=True)

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
print(f"    共 {len(all_codes)} 只")

# ===== Step 2: 大盘环境检测 =====
print("\n  [2/5] 大盘环境检测...")
indices = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
}
market_env = {"up": 0, "down": 0, "flat": 0, "total": 0}
index_status = {}

for idx_name, idx_code in indices.items():
    try:
        prefix = idx_code[:2]
        raw_code = idx_code[2:]
        q = client.quotes(symbol=[raw_code])
        if q is not None and len(q) > 0:
            row = q.iloc[0]
            price = float(row.get("price", 0) or 0)
            last_close = float(row.get("last_close", 0) or 0)
            if price > 0 and last_close > 0:
                chg = (price / last_close - 1) * 100
                index_status[idx_name] = {"price": price, "chg": chg}
    except:
        pass

# 统计涨跌家数 (用全市场扫描第一批发行情)
up_count = 0
down_count = 0
flat_count = 0
total_count = 0
sample_codes = [c for c, _ in all_codes[:500]]

for i in range(0, len(sample_codes), 80):
    batch = sample_codes[i:i+80]
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
            if chg > 0.5:
                up_count += 1
            elif chg < -0.5:
                down_count += 1
            else:
                flat_count += 1
    except:
        pass
    time.sleep(0.1)

up_ratio = up_count / total_count * 100 if total_count > 0 else 50
down_ratio = down_count / total_count * 100 if total_count > 0 else 50

# 判断市场环境
market_score = 0  # -2 到 +2
if up_ratio >= 60:
    market_score = 2
    env_label = "🟢 强势（涨多跌少）"
elif up_ratio >= 50:
    market_score = 1
    env_label = "🟢 偏强"
elif up_ratio >= 40:
    market_score = 0
    env_label = "🟡 震荡"
elif up_ratio >= 30:
    market_score = -1
    env_label = "🟠 偏弱"
else:
    market_score = -2
    env_label = "🔴 弱势（跌多涨少）"

print(f"    {env_label}")
print(f"    涨: {up_count}({up_ratio:.0f}%)  跌: {down_count}({down_ratio:.0f}%)  平: {flat_count}")
for idx_name, info in index_status.items():
    arrow = "📈" if info["chg"] > 0 else "📉"
    print(f"    {arrow} {idx_name}: {info['price']:.2f} ({info['chg']:+.2f}%)")

# ===== Step 3: 批量行情扫描 =====
print(f"\n  [3/5] 行情扫描 (找今日涨幅 3-7%)...")
candidates = []
batch_size = 80
codes = [c for c, _ in all_codes]

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
            vol = float(q.get("vol", 0) or 0)

            if price <= 0 or prev <= 0:
                continue

            chg_pct = (price / prev - 1) * 100

            # 过滤条件
            is_20cm = code.startswith("30") or code.startswith("68")
            limit_pct = 20 if is_20cm else 10
            is_limit_up = chg_pct >= (limit_pct - 0.5)

            if (3 <= chg_pct <= 7 and not is_limit_up
                and price > 2 and amount > 30000000):
                upper_shadow = max(0, (high - max(price, open_p)) / open_p * 100) if open_p > 0 else 0
                candidates.append({
                    "code": code, "price": price, "prev": prev,
                    "open": open_p, "high": high, "low": low,
                    "chg": chg_pct, "amount": amount, "vol": vol,
                    "upper_shadow": upper_shadow,
                })
    except:
        pass
    if (i // batch_size + 1) % 20 == 0:
        print(f"    进度: {min(i+batch_size, len(codes))}/{len(codes)}, 已发现 {len(candidates)} 候选")

# 放宽条件
if len(candidates) < 5:
    print("    候选不足，放宽到 2-8%...")
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
                amount = float(q.get("amount", 0) or 0)
                vol = float(q.get("vol", 0) or 0)
                if price <= 0 or prev <= 0:
                    continue
                chg_pct = (price / prev - 1) * 100
                is_20cm = code.startswith("30") or code.startswith("68")
                limit_pct = 20 if is_20cm else 10
                is_limit_up = chg_pct >= (limit_pct - 0.5)
                already_in = any(c["code"] == code for c in candidates)
                if (2 <= chg_pct <= 8 and not is_limit_up
                    and price > 2 and amount > 20000000 and not already_in):
                    upper_shadow = max(0, (high - max(price, open_p)) / open_p * 100) if open_p > 0 else 0
                    candidates.append({
                        "code": code, "price": price, "prev": prev,
                        "open": open_p, "high": high, "low": float(q.get("low", 0) or 0),
                        "chg": chg_pct, "amount": amount, "vol": vol,
                        "upper_shadow": upper_shadow,
                    })
        except:
            pass
        time.sleep(0.1)
    print(f"    放宽后: {len(candidates)} 只")

if len(candidates) == 0:
    print("  ❌ 全市场没有符合条件的强势股")
    exit()

print(f"    今日涨幅3-7%+非ST+非涨停+>3000万: {len(candidates)} 只")

# 按涨幅排序取前200做深度分析
candidates.sort(key=lambda x: x["chg"], reverse=True)
candidates = candidates[:200]

# ===== Step 4: 技术面分析 =====
print(f"\n  [4/5] 技术面深度分析 ({len(candidates)} 只)...")
results = []

for idx, cand in enumerate(candidates):
    code = cand["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
            continue

        df = bars.copy()
        close = df["close"].astype(float)
        vol = df["vol"].astype(float)

        cur = float(close.iloc[-1])
        ma5 = float(close.rolling(5).mean().iloc[-1])
        ma10 = float(close.rolling(10).mean().iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else 0

        # 量比 = 今日成交量 / 前5日均量
        v_today = float(vol.iloc[-1])
        v_5avg = float(vol.iloc[-6:-1].mean()) if len(vol) >= 6 else float(vol.mean())
        vr = v_today / v_5avg if v_5avg > 0 else 1.0

        chg_3d = (cur / float(close.iloc[-4]) - 1) * 100 if len(close) >= 4 else 0
        chg_5d = (cur / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
        dev = (cur / ma20 - 1) * 100 if ma20 > 0 else 0

        stock = StockDataFrame.retype(df)
        try: rsi6 = float(stock["rsi_6"].dropna().iloc[-1])
        except: rsi6 = 50
        try: rsi14 = float(stock["rsi_14"].dropna().iloc[-1])
        except: rsi14 = 50
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

        # 连涨天数
        up_days = 0
        for d in range(1, min(10, len(close))):
            if float(close.iloc[-d]) > float(close.iloc[-d-1]):
                up_days += 1
            else:
                break

        # =============================
        # 评分: 正面分 75 + 安全罚分
        # =============================
        score = 0
        details = []
        penalty = 0

        # --- 正面分 ---
        # 1. 均线 (max 20)
        if cur > ma5 > ma10 > ma20:
            if ma60 and ma20 > ma60:
                score += 20; details.append(("均线完美多头", 20))
            else:
                score += 17; details.append(("短期多头", 17))
        elif cur > ma5 > ma10:
            score += 12; details.append(("站上MA5/10", 12))
        elif cur > ma5:
            score += 7; details.append(("站上MA5", 7))
        elif cur > ma20:
            score += 4
        else:
            score += 1

        # 2. RSI (max 20)
        if 50 <= rsi14 <= 65:
            score += 20; details.append((f"RSI{rsi14:.0f}健康", 20))
        elif 45 <= rsi14 < 50:
            score += 14; details.append((f"RSI{rsi14:.0f}", 14))
        elif 65 < rsi14 <= 72:
            score += 12
        elif 35 <= rsi14 < 45:
            score += 8
        else:
            score += 3

        # 3. MACD (max 15)
        if dif > dea > 0 and macdh > macdh_prev:
            score += 15; details.append(("MACD多头加速", 15))
        elif dif > dea > 0:
            score += 12; details.append(("MACD多头", 12))
        elif dif > dea and dif > 0:
            score += 8
        elif dif > 0:
            score += 5
        elif dif > dea:
            score += 3

        # 4. 量能 (max 10)
        if 1.1 <= vr <= 2.5:
            score += 10; details.append((f"量比{vr:.1f}x", 10))
        elif 0.8 <= vr < 1.1:
            score += 6
        elif vr > 2.5:
            score += 7
        else:
            pass  # 缩量不加分

        # 5. 乖离 (max 5)
        if 2 <= dev <= 12:
            score += 5
        elif -2 <= dev < 2:
            score += 3
        elif 12 < dev <= 18:
            score += 2

        # 6. 涨幅适中 (5)
        if 3 <= cand["chg"] <= 5:
            score += 5
        elif 5 < cand["chg"] <= 7:
            score += 3

        # --- 🔑 安全罚分 ---
        # 乖离过大
        if dev > 25:
            penalty += 15; details.append((f"乖离{dev:.0f}%严重", -15))
        elif dev > 20:
            penalty += 10; details.append((f"乖离{dev:.0f}%偏高", -10))
        elif dev > 15:
            penalty += 5; details.append((f"乖离{dev:.0f}%", -5))

        # RSI超买
        if rsi14 > 75:
            penalty += 10; details.append((f"RSI{rsi14:.0f}超买", -10))
        elif rsi14 > 70:
            penalty += 5

        # 缩量严重
        if vr < 0.3:
            penalty += 20; details.append((f"无量{vr:.1f}x", -20))
        elif vr < 0.5:
            penalty += 10; details.append((f"缩量{vr:.1f}x", -10))
        elif vr < 0.8:
            penalty += 3

        # 连涨透支
        if chg_5d > 15:
            penalty += 10; details.append((f"5日+{chg_5d:.0f}%透支", -10))
        elif chg_5d > 10:
            penalty += 5

        # 连涨天数
        if up_days >= 5:
            penalty += 8; details.append((f"连涨{up_days}天", -8))
        elif up_days >= 4:
            penalty += 4

        # 高价股
        if cur > 80:
            penalty += 5; details.append((f"高价{cur:.0f}元", -5))
        elif cur > 50:
            penalty += 2

        # 上影线
        us = cand["upper_shadow"]
        if us > 3:
            penalty += min(5, int(us)); details.append((f"上影{us:.1f}%", -min(5, int(us))))

        # KDJ超买
        if j > 100:
            penalty += 3; details.append((f"J={j:.0f}超买", -3))

        score -= penalty
        score = max(0, min(100, score))

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": cand["price"],
            "chg_today": cand["chg"], "prev": cand["prev"],
            "rsi14": rsi14, "rsi6": rsi6,
            "vr": vr, "chg_3d": chg_3d, "chg_5d": chg_5d,
            "dev": dev, "score": score, "details": details,
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
            "dif": dif, "dea": dea, "macdh": macdh,
            "k": k, "j": j, "upper_shadow": us,
            "amount": cand["amount"], "up_days": up_days,
        })
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)
print(f"    分析完成: {len(results)} 只")

# ===== Step 5: 获取名称 =====
print(f"\n  [5/5] 获取股票名称...")
need_names = [r for r in results[:15] if not r["name"]]
if need_names:
    try:
        url = "https://qt.gtimg.cn/q=" + ",".join(
            [f"sz{r['code']}" if r['code'][0] in "023" else f"sh{r['code']}" for r in need_names])
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

# ===== 输出 TOP15 + 风险标签 =====
print(f"\n{'='*72}")
print(f"  🏆 动量策略 TOP15  (大盘: {env_label})")
print(f"{'='*72}")

for i, r in enumerate(results[:15]):
    name_str = r["name"] or f"({r['code']})"
    bar_len = max(0, int(r["score"] / 5))
    bar = "▓" * bar_len + "░" * (20 - bar_len)

    # 风险标签
    warnings = []
    if r["vr"] < 0.3: warnings.append("⚠️无量")
    elif r["vr"] < 0.5: warnings.append("⚠️缩量")
    if r["rsi14"] > 70: warnings.append("⚠️超买")
    if r.get("dev", 0) > 20: warnings.append("🔴乖离大")
    elif r.get("dev", 0) > 15: warnings.append("⚠️乖离偏高")
    if r["chg_5d"] > 12: warnings.append("⚠️已透支")
    if r["up_days"] >= 4: warnings.append(f"⚠️连涨{r['up_days']}天")
    if r["upper_shadow"] > 3: warnings.append("⚠️上影")
    if r["j"] > 100: warnings.append("⚠️J超买")
    if r["price"] > 80: warnings.append("⚠️高价")

    if warnings:
        tag = "🚫险" if r["score"] < 60 else ("🔴危" if any(w.startswith("🔴") for w in warnings) else "⚠️慎")
    else:
        tag = "🟢买" if r["score"] >= 75 else ("🟡观" if r["score"] >= 60 else "⚪等")

    warn_str = " ".join(warnings) if warnings else "无风险"

    print(f"\n  #{i+1} {name_str}({r['code']})  ¥{r['price']:.2f}  今日{r['chg_today']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  RSI14={r['rsi14']:.0f}  量比={r['vr']:.1f}x  乖离={r['dev']:.1f}%  3日={r['chg_3d']:+.1f}%  5日={r['chg_5d']:+.1f}%")
    print(f"  MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f}  KDJ-J={r['j']:.0f}  风险: {warn_str}")
    print(f"  MA5={r['ma5']:.2f}  MA10={r['ma10']:.2f}  MA20={r['ma20']:.2f}  MA60={r['ma60']:.2f}")

# ===== 最终推荐（安全门） =====
if results:
    # 安全过滤: 量比>=0.5, RSI<=70, 乖离<=20, 5日涨幅<=12
    safe = [r for r in results
            if r["vr"] >= 0.5
            and r["rsi14"] <= 70
            and r.get("dev", 0) <= 20
            and r["chg_5d"] <= 12
            and r["up_days"] < 4]
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]

    # 风险检查
    risk_flags = []
    if best["vr"] < 0.3: risk_flags.append("低流动性")
    if best.get("dev", 0) > 20: risk_flags.append("乖离过大")
    if best["rsi14"] > 70: risk_flags.append("RSI超买")
    if best["chg_5d"] > 12: risk_flags.append("5日涨幅已透支")
    if best["up_days"] >= 4: risk_flags.append(f"连涨{best['up_days']}天")
    if best["j"] > 100: risk_flags.append("KDJ超买")

    # 大盘弱时加分阈值
    score_threshold = 75 if market_score >= 0 else 80

    print(f"\n{'='*72}")
    print(f"  🎯 最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'='*72}")
    print(f"\n  现价: ¥{best['price']:.2f}    今日涨幅: {best['chg_today']:+.1f}%")
    print(f"  大盘: {env_label}")

    if market_score <= -2:
        print(f"\n  🔴 大盘环境极弱（涨{up_ratio:.0f}%跌{down_ratio:.0f}%），不建议买入。空仓等待。")
    elif risk_flags:
        print(f"\n  ⚠️ 风险: {', '.join(risk_flags)} — 不推荐买入")
        print(f"  今日市场不适合动量策略，建议空仓等待")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 今日尾盘直接买入")
        print(f"  目标: ¥{best['price']*1.04:.2f}(+4%) ~ ¥{best['price']*1.05:.2f}(+5%)")
        print(f"  止损: ¥{best['price']*0.97:.2f}(-3%)")
        print(f"  卖出: 明天盘中达标即卖")
        print(f"  仓位: ≤ 25%")
    elif best["score"] >= 65:
        print(f"\n  ⚠ 评分 {best['score']}/100，勉强可关注但不建议重仓")
        print(f"  如果要做: 仓位 ≤ 10%，止损 ¥{best['price']*0.97:.2f}(-3%)")
    else:
        print(f"\n  ⚠ 评分不足 {best['score']}/100，不建议买入。等更好的机会。")

print(f"\n  ⚠ 以上为技术面分析，不构成投资建议")
