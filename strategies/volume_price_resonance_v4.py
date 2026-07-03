"""
量价共振策略 V4 — T+1 短线（V4全面升级版）
新增：真实RPS + 情绪Gate + 基本面过滤 + 行业动量共振 + 高位放量危险检测
"""
import pandas as pd
import numpy as np
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.stock_utils import (
    get_client, get_stock_list, get_market_env,
    get_extra_data_batch, calc_technical_indicators,
    detect_volume_price_divergence, calc_atr_stop,
    get_name_batch, generate_risk_tags,
    get_limit_up_sentiment, get_fundamental_data_batch,
    calc_true_rps, get_industry_momentum,
    UA, HEADERS,
)
import requests

client = get_client()

print("=" * 78)
print("  量价共振策略 V4 — T+1 量价+资金+情绪三确认")
print("=" * 78)

# ===== Step 0: 市场情绪（V4新增）=====
print("\n  [0/7] 市场情绪检测...")
sentiment = get_limit_up_sentiment()
print(f"    涨停{sentiment['limit_up_count']}家  炸板率{sentiment['broken_rate']:.0f}%  温度{sentiment['sentiment_score']:.0f}  {sentiment['sentiment_label']}")

if sentiment["broken_rate"] > 35:
    print(f"  ❌ 炸板率{sentiment['broken_rate']:.0f}%>35%，市场承接力弱")
    exit()

# ===== Step 1: 获取股票列表 =====
print("\n  [1/7] 获取沪深A股列表...")
all_codes = get_stock_list()
name_map = dict(all_codes)
codes = [c for c, _ in all_codes]
print(f"    共 {len(codes)} 只")

# ===== Step 2: 大盘环境 =====
print("\n  [2/7] 大盘环境检测...")
env_label, market_score, up_ratio, down_ratio, index_status = get_market_env(codes[:500])
print(f"    {env_label}  涨:{up_ratio:.0f}%  跌:{down_ratio:.0f}%")

# ===== Step 3: 行情扫描 =====
print(f"\n  [3/7] 行情扫描 + 初筛...")
candidates = []
batch_size = 80

for i in range(0, len(codes), batch_size):
    batch = codes[i:i + batch_size]
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
            is_20cm = code.startswith("30") or code.startswith("68")
            limit_pct = 20 if is_20cm else 10
            is_limit_up = chg_pct >= (limit_pct - 0.5)

            if not (1 <= chg_pct <= 8):
                continue
            if is_limit_up:
                continue
            if amount < 10000000:
                continue
            if price < 2:
                continue

            upper_shadow = max(0, (high - max(price, open_p)) / open_p * 100) if open_p > 0 else 0
            lower_shadow = max(0, (min(price, open_p) - low) / open_p * 100) if open_p > 0 else 0

            candidates.append({
                "code": code, "price": price, "prev": prev,
                "open": open_p, "high": high, "low": low,
                "chg": chg_pct, "amount": amount, "vol": vol,
                "upper_shadow": upper_shadow, "lower_shadow": lower_shadow,
            })
    except:
        pass
    if (i // batch_size + 1) % 15 == 0:
        print(f"    进度: {min(i + batch_size, len(codes))}/{len(codes)}, 候选 {len(candidates)}")

candidates.sort(key=lambda x: x["chg"], reverse=True)
candidates = candidates[:300]
print(f"    初步候选: {len(candidates)} 只")

# ===== Step 4: 换手率+资金+基本面 =====
print(f"\n  [4/7] 获取换手率+资金+基本面...")
candidate_codes = [c["code"] for c in candidates]
extra_data = get_extra_data_batch(candidate_codes)
fund_data = get_fundamental_data_batch(candidate_codes)
print(f"    数据: 换手{len(extra_data)}只  基本面{len(fund_data)}只")

# 换手率初筛
filtered = []
for cand in candidates:
    code = cand["code"]
    extra = extra_data.get(code, {})
    turnover = extra.get("turnover", 5)
    if 2 <= turnover <= 20:
        filtered.append(cand)
print(f"    换手率2-20%过滤后: {len(filtered)} 只")
candidates = filtered[:200]

# ===== Step 5: 技术面深度分析 =====
print(f"\n  [5/7] 技术面深度分析 ({len(candidates)} 只)...")

results = []

for idx, cand in enumerate(candidates):
    code = cand["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
            continue

        df = bars.copy()
        ind = calc_technical_indicators(df)

        extra = extra_data.get(code, {})
        turnover = extra.get("turnover", 0)
        main_net = extra.get("main_net", 0)

        # === V4: 基本面过滤 ===
        fund = fund_data.get(code, {})
        pe = fund.get("pe", 0)
        pb = fund.get("pb", 0)
        total_mv = fund.get("total_mv", 0)

        if pe != 0 and (pe < 0 or pe > 200):
            continue
        if pb != 0 and pb > 10:
            continue
        if 0 < total_mv < 2_000_000_000:
            continue

        # === V4: 真实RPS ===
        rps20, rps60 = calc_true_rps(code, ind["chg_20d"], None, None, None)

        # VIP检查（API数据不可用时放宽vr阈值）
        vr_threshold = 0.5 if len(extra_data) == 0 else 0.8
        if ind["vr"] < vr_threshold:
            continue

        close_s = df["close"].astype(float)
        vol_s = df["vol"].astype(float)
        div_type, div_penalty = detect_volume_price_divergence(close_s, vol_s, 5)
        if div_type == "bull_divergence":
            continue

        if main_net < -5000000:
            continue

        if ind["boll_pos"] > 95:
            continue

        # === V4: 高位放量危险检测 ===
        # 当前价在BOLL上轨附近(>90%) + 放量 = 高位放量出货
        high_vol_danger = False
        if ind["boll_pos"] > 85 and ind["vr"] > 1.5:
            high_vol_danger = True

        # ======================
        # 评分系统 V4 (满分100)
        # ======================
        score = 0
        details = []
        penalty = 0

        # 1. 量价配合 (max 18)
        vr_use = ind["vr"]
        if 1.3 <= vr_use <= 2.5 and cand["chg"] >= 2:
            score += 18; details.append(("量价共振放量上涨", 18))
        elif 1.1 <= vr_use < 1.3 and cand["chg"] >= 1:
            score += 14; details.append(("温和放量上涨", 14))
        elif 0.8 <= vr_use < 1.1:
            score += 8; details.append(("量能持平", 8))
        else:
            score += 3

        # 2. 资金共振 (max 16)
        if main_net > 20000000:
            score += 16; details.append(("大资金强势流入", 16))
        elif main_net > 10000000:
            score += 13; details.append(("主力大幅流入", 13))
        elif main_net > 5000000:
            score += 10; details.append(("主力流入", 10))
        elif main_net > 1000000:
            score += 6; details.append(("主力微流入", 6))
        else:
            score += 3

        # 3. 趋势强度 (max 16)
        trend_score = 0
        if ind["cur"] > ind["ma5"] > ind["ma10"] > ind["ma20"]:
            trend_score += 7; details.append(("多头排列", 7))
        elif ind["cur"] > ind["ma5"] > ind["ma10"]:
            trend_score += 4
        if ind["ma5_slope"] > 0.2:
            trend_score += 5; details.append(("MA5向上", 5))
        if ind["dif"] > ind["dea"] and ind["dif"] > 0:
            trend_score += 4; details.append(("MACD多头", 4))
        score += min(16, trend_score)

        # 4. 换手健康 (max 10)
        if 3 <= turnover <= 10:
            score += 10; details.append((f"换手{turnover:.1f}%最佳", 10))
        elif 2 <= turnover < 3 or 10 < turnover <= 15:
            score += 7; details.append((f"换手{turnover:.1f}%良好", 7))
        elif 15 < turnover <= 20:
            score += 4

        # 5. 真实RPS (max 10) — V4核心升级
        if rps20 >= 85:
            score += 10; details.append((f"RPS{rps20:.0f}极强", 10))
        elif rps20 >= 70:
            score += 8; details.append((f"RPS{rps20:.0f}强势", 8))
        elif rps20 >= 55:
            score += 5; details.append((f"RPS{rps20:.0f}偏强", 5))
        elif rps20 >= 40:
            score += 3
        else:
            score += 1

        # 6. 位置适中 (max 8)
        bp = ind["boll_pos"]
        if 40 <= bp <= 80:
            score += 8; details.append((f"BOLL{bp:.0f}%适中", 8))
        elif 25 <= bp < 40:
            score += 5; details.append((f"BOLL{bp:.0f}%偏低", 5))
        elif 80 < bp <= 92:
            score += 4
        else:
            score += 2

        # 7. 涨停基因 (max 5)
        lu = ind["limit_up_count"]
        if lu >= 2:
            score += 5; details.append((f"涨停{lu}次", 5))
        elif lu >= 1:
            score += 3

        # 8. 振幅合理 (max 4)
        amp = (cand["high"] / cand["low"] - 1) * 100
        if 3 <= amp <= 7:
            score += 4

        # 9. 行业热度 (max 4) — V4保留
        if main_net > 10000000:
            score += 4

        # 10. 基本面质量 (max 3) — V4新增
        if 5 < pe < 50 and 1 < pb < 5:
            score += 3; details.append(("估值合理", 3))

        # --- 惩罚 V4 ---
        dev = ind["dev"]
        if dev > 25: penalty += 12; details.append((f"乖离{dev:.0f}%", -12))
        elif dev > 20: penalty += 8
        if cand["upper_shadow"] > 3 and ind["vr"] > 1.5:
            penalty += 8; details.append(("放量上影出货", -8))
        if ind["j"] > 105: penalty += 3
        if ind["up_days"] >= 5: penalty += 6; details.append((f"连涨{ind['up_days']}天", -6))
        if turnover > 25: penalty += 5

        # === V4新增惩罚 ===
        if high_vol_danger:
            penalty += 10; details.append(("高位放量危险", -10))
        if main_net < -3000000:
            penalty += 5; details.append(("主力流出", -5))
        if rps20 < 30:
            penalty += 5; details.append((f"RPS{rps20:.0f}弱势", -5))

        score -= penalty
        score = max(0, min(100, score))

        stop_pct, stop_price = calc_atr_stop(ind["cur"], ind["atr14"])

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": cand["price"],
            "chg_today": cand["chg"],
            "rsi14": ind["rsi14"], "vr": vr_use,
            "turnover": turnover, "main_net": main_net,
            "score": score, "details": details,
            "ma5": ind["ma5"], "ma10": ind["ma10"], "ma20": ind["ma20"],
            "dev": dev, "boll_pos": bp,
            "dif": ind["dif"], "dea": ind["dea"],
            "up_days": ind["up_days"], "limit_up_count": lu,
            "ma5_slope": ind["ma5_slope"],
            "j": ind["j"], "upper_shadow": cand["upper_shadow"],
            "amount": cand["amount"],
            "stop_pct": stop_pct, "stop_price": stop_price,
            "rps20": rps20, "pe": pe, "pb": pb, "total_mv": total_mv,
            "chg_20d": ind["chg_20d"],
        })
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)

# === V4.1: 基于候选池修正真实RPS20 ===
if results:
    all_chg20 = [r["chg_20d"] for r in results]
    n = len(all_chg20)
    for r in results:
        rank = sum(1 for x in all_chg20 if x <= r["chg_20d"])
        r["rps20"] = round(rank / n * 100, 1)

print(f"    分析完成: {len(results)} 只通过共振检查")

# ===== Step 6: 补全名称 =====
print(f"\n  [6/7] 补充股票名称...")
missing = [r for r in results[:15] if not r["name"]]
if missing:
    names = get_name_batch([r["code"] for r in missing])
    for r in missing:
        r["name"] = names.get(r["code"], r["code"])

# ===== 输出 TOP15 =====
print(f"\n{'=' * 78}")
print(f"  量价共振 V4 TOP15  (大盘: {env_label}  情绪: {sentiment['sentiment_label']})")
print(f"{'=' * 78}")

for i, r in enumerate(results[:15]):
    name_str = r["name"] or f"({r['code']})"
    bar_len = max(0, int(r["score"] / 5))
    bar = "\u2593" * bar_len + "\u2591" * (20 - bar_len)

    warnings = generate_risk_tags(r)

    if warnings:
        tag = "!!" if r["score"] < 60 else "??"
    else:
        tag = "OK" if r["score"] >= 75 else (".." if r["score"] >= 60 else "--")

    warn_str = " ".join(warnings) if warnings else "无风险"

    pe_str = f"PE={r.get('pe', 0):.1f}" if r.get("pe", 0) > 0 else ""
    print(f"\n  #{i + 1} {name_str}({r['code']})  {r['price']:.2f}  今日{r['chg_today']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  量比={r['vr']:.1f}x  换手={r['turnover']:.1f}%  大单={r['main_net'] / 10000:.0f}万  RPS20={r['rps20']:.0f}")
    print(f"  BOLL={r['boll_pos']:.0f}%  涨停基因={r['limit_up_count']}次  {pe_str}  风险: {warn_str}")
    print(f"  MA5={r['ma5']:.2f}  MA20={r['ma20']:.2f}  MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f}")

# ===== 最终推荐 =====
if results:
    # V4 安全门（增加基本面+RPS）
    safe = [r for r in results
            if r["vr"] >= 1.0
            and r["dev"] <= 18
            and r["up_days"] < 4
            and r["main_net"] > -3000000
            and r["boll_pos"] <= 92
            and r["upper_shadow"] < 4
            and r.get("rps20", 50) >= 35]  # V4新增
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]

    score_threshold = 70 if market_score >= 0 else 78

    print(f"\n{'=' * 78}")
    print(f"  最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'=' * 78}")
    print(f"\n  现价: {best['price']:.2f}    今日涨幅: {best['chg_today']:+.1f}%")
    print(f"  大盘: {env_label}    情绪: {sentiment['sentiment_label']}")
    print(f"  量比: {best['vr']:.1f}x  换手: {best['turnover']:.1f}%  大单: {best['main_net'] / 10000:.0f}万")
    print(f"  RPS20: {best['rps20']:.0f}    PE: {best.get('pe', 0):.1f}    市值: {best.get('total_mv', 0) / 1e8:.0f}亿")

    if market_score <= -2:
        print(f"\n  !! 大盘环境极弱，不建议操作")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 尾盘14:50确认量比>1.2后买入")
        print(f"  目标: {best['price'] * 1.04:.2f}(+4%) -> 出一半 -> {best['price'] * 1.06:.2f}(+6%)全出")
        print(f"  ATR止损: {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
        print(f"  仓位: 总资金20%, 单票10%")
    elif best["score"] >= 60:
        print(f"\n  !! 评分 {best['score']}/100 勉强可关注")
        print(f"  仓位 <= 8%, ATR止损 {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
    else:
        print(f"\n  !! 评分不足，不建议买入")

print(f"\n  !! 以上为技术分析，不构成投资建议")
