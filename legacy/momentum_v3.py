"""
动量策略 V3 — T+1 短线（全面升级版）
新增换手率、大单净量、量价背离、RPS、均线斜率、布林带宽度、涨停基因、ATR动态止损
"""
import pandas as pd
import numpy as np
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stock_utils import (
    get_client, get_stock_list, get_market_env,
    get_extra_data_batch, calc_technical_indicators,
    detect_volume_price_divergence, calc_atr_stop,
    get_name_batch, get_hot_sectors, generate_risk_tags,
    UA, HEADERS,
)
import requests

client = get_client()

print("=" * 76)
print("  动量策略 V3 — T+1 今日买入 → 明日卖出（全面升级）")
print("=" * 76)

# ===== Step 1: 获取股票列表 =====
print("\n  [1/6] 获取沪深A股列表...")
all_codes = get_stock_list()
name_map = dict(all_codes)
codes = [c for c, _ in all_codes]
print(f"    共 {len(codes)} 只")

# ===== Step 2: 大盘环境检测 =====
print("\n  [2/6] 大盘环境检测...")
env_label, market_score, up_ratio, down_ratio, index_status = get_market_env(codes[:500])
print(f"    {env_label}")
print(f"    涨: {up_ratio:.0f}%  跌: {down_ratio:.0f}%")
for idx_name, info in index_status.items():
    arrow = "+" if info["chg"] > 0 else ""
    print(f"    {arrow} {idx_name}: {info['price']:.2f} ({info['chg']:+.2f}%)")

# 热门题材
print("\n    今日热门题材 TOP8:")
hot = get_hot_sectors()
for tag, cnt in hot[:8]:
    print(f"      {tag}: {cnt}只")

# ===== Step 3: 行情扫描（涨幅 3-7%）=====
print(f"\n  [3/6] 行情扫描 (找今日涨幅 3-7%)...")
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

            if price <= 0 or prev <= 0:
                continue

            chg_pct = (price / prev - 1) * 100
            is_20cm = code.startswith("30") or code.startswith("68")
            limit_pct = 20 if is_20cm else 10
            is_limit_up = chg_pct >= (limit_pct - 0.5)

            if (3 <= chg_pct <= 7 and not is_limit_up
                    and price > 2 and amount > 30000000):
                upper_shadow = max(0, (high - max(price, open_p)) / open_p * 100) if open_p > 0 else 0
                lower_shadow = max(0, (min(price, open_p) - low) / open_p * 100) if open_p > 0 else 0
                candidates.append({
                    "code": code, "price": price, "prev": prev,
                    "open": open_p, "high": high, "low": low,
                    "chg": chg_pct, "amount": amount,
                    "upper_shadow": upper_shadow, "lower_shadow": lower_shadow,
                })
    except:
        pass
    if (i // batch_size + 1) % 15 == 0:
        print(f"    进度: {min(i + batch_size, len(codes))}/{len(codes)}, 候选 {len(candidates)}")

# 放宽条件
if len(candidates) < 10:
    print("    候选不足，放宽到 2-8%...")
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
                    lower_shadow = max(0, (min(price, open_p) - low) / open_p * 100) if open_p > 0 else 0
                    candidates.append({
                        "code": code, "price": price, "prev": prev,
                        "open": open_p, "high": high, "low": low,
                        "chg": chg_pct, "amount": amount,
                        "upper_shadow": upper_shadow, "lower_shadow": lower_shadow,
                    })
        except:
            pass
    print(f"    放宽后: {len(candidates)} 只")

if len(candidates) == 0:
    print("  ❌ 全市场没有符合条件的强势股")
    exit()

candidates.sort(key=lambda x: x["chg"], reverse=True)
candidates = candidates[:200]
print(f"    深度分析候选: {len(candidates)} 只")

# ===== Step 4: 获取换手率+资金流向 =====
print(f"\n  [4/6] 获取换手率+大单净量 (东方财富)...")
candidate_codes = [c["code"] for c in candidates]
extra_data = get_extra_data_batch(candidate_codes)
print(f"    获取到 {len(extra_data)} 只额外数据")

# ===== Step 5: 技术面深度分析 =====
print(f"\n  [5/6] 技术面深度分析...")
results = []

for idx, cand in enumerate(candidates):
    code = cand["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
            continue

        df = bars.copy()
        ind = calc_technical_indicators(df)

        # 换手率和大单净量
        extra = extra_data.get(code, {})
        turnover = extra.get("turnover", 5)
        main_net = extra.get("main_net", 0)
        vr_em = extra.get("volume_ratio", ind["vr"])  # 东方财富量比，fallback到通达信

        # 量价背离检测
        close_s = df["close"].astype(float)
        vol_s = df["vol"].astype(float)
        div_type, div_penalty = detect_volume_price_divergence(close_s, vol_s, 5)

        # RPS（简化为 stock vs market 近似）
        rps = max(0, min(100, 50 + ind["chg_5d"] * 3 - ind["chg_20d"] * 1.5 + ind["ma5_slope"] * 5))

        # ======================
        # 评分系统 V3 (满分100)
        # ======================
        score = 0
        details = []
        penalty = 0

        # 1. 均线排列 (max 15) + 斜率
        if ind["cur"] > ind["ma5"] > ind["ma10"] > ind["ma20"]:
            if ind["ma60"] > 0 and ind["ma20"] > ind["ma60"]:
                if ind["ma5_slope"] > 0.3:
                    score += 15; details.append(("均线完美多头+向上", 15))
                else:
                    score += 13; details.append(("均线完美多头(走平)", 13))
            else:
                score += 11; details.append(("短期多头排列", 11))
        elif ind["cur"] > ind["ma5"] > ind["ma10"]:
            score += 8; details.append(("站上MA5/10", 8))
        elif ind["cur"] > ind["ma5"]:
            score += 5; details.append(("站上MA5", 5))
        elif ind["cur"] > ind["ma20"]:
            score += 3; details.append(("站上MA20", 3))
        else:
            score += 1

        # 2. RSI (max 12)
        rsi14 = ind["rsi14"]
        if 50 <= rsi14 <= 65:
            score += 12; details.append((f"RSI{rsi14:.0f}健康", 12))
        elif 45 <= rsi14 < 50:
            score += 9; details.append((f"RSI{rsi14:.0f}中性", 9))
        elif 65 < rsi14 <= 72:
            score += 7; details.append((f"RSI{rsi14:.0f}偏高", 7))
        elif 35 <= rsi14 < 45:
            score += 5
        else:
            score += 2

        # 3. MACD (max 12)
        if ind["dif"] > ind["dea"] > 0 and ind["macdh"] > ind["macdh_prev"]:
            score += 12; details.append(("MACD多头加速", 12))
        elif ind["dif"] > ind["dea"] > 0:
            score += 10; details.append(("MACD多头", 10))
        elif ind["dif"] > ind["dea"] and ind["dif"] > 0:
            score += 7
        elif ind["dif"] > 0:
            score += 4
        elif ind["dif"] > ind["dea"]:
            score += 2

        # 4. 量能 (max 10)
        vr_use = max(ind["vr"], vr_em)  # 取两者较大值
        if 1.1 <= vr_use <= 2.5:
            score += 10; details.append((f"放量{vr_use:.1f}x", 10))
        elif 0.8 <= vr_use < 1.1:
            score += 6; details.append((f"量{vr_use:.1f}x", 6))
        elif vr_use > 2.5:
            score += 7; details.append((f"巨量{vr_use:.1f}x", 7))

        # 5. 乖离 (max 6)
        dev = ind["dev"]
        if 2 <= dev <= 12:
            score += 6; details.append((f"乖离{dev:.1f}%适中", 6))
        elif -2 <= dev < 2:
            score += 4
        elif 12 < dev <= 18:
            score += 3
        else:
            score += 1

        # 6. 涨幅 (max 4)
        if 3 <= cand["chg"] <= 5:
            score += 4; details.append(("涨幅温和", 4))
        elif 5 < cand["chg"] <= 7:
            score += 2

        # 7. 换手率 (max 8)
        if 2 <= turnover <= 10:
            score += 8; details.append((f"换手{turnover:.1f}%健康", 8))
        elif 10 < turnover <= 15:
            score += 5; details.append((f"换手{turnover:.1f}%活跃", 5))
        elif 1 <= turnover < 2:
            score += 3; details.append((f"换手{turnover:.1f}%偏低", 3))
        else:
            score += 1

        # 8. 量价配合 (max 12)
        if div_type is None and vr_use >= 1.0:
            score += 12; details.append(("量价配合良好", 12))
        elif div_type is None:
            score += 8; details.append(("量价正常", 8))
        elif div_type == "bull_divergence":
            # 量价背离：涨+缩量 = 不减分（由penalty处理），但也不加分
            score += 2; details.append(("量价背离", 2))
        else:
            score += 6

        # 9. 大单净量 (max 10)
        if main_net > 10000000:
            score += 10; details.append(("主力大幅流入", 10))
        elif main_net > 5000000:
            score += 8; details.append(("主力流入", 8))
        elif main_net > 0:
            score += 5; details.append(("主力微流入", 5))
        elif main_net > -5000000:
            score += 2
        else:
            score += 0  # 主力流出不加分

        # 10. RPS相对强弱 (max 8)
        if rps >= 80:
            score += 8; details.append((f"RPS{rps:.0f}极强", 8))
        elif rps >= 65:
            score += 6; details.append((f"RPS{rps:.0f}强势", 6))
        elif rps >= 50:
            score += 3
        else:
            score += 1

        # 11. 涨停基因 (max 5)
        lu = ind["limit_up_count"]
        if lu >= 3:
            score += 5; details.append((f"涨停{lu}次活跃", 5))
        elif lu >= 1:
            score += 3; details.append((f"涨停{lu}次", 3))

        # --- 惩罚系统 ---
        # 乖离
        if dev > 25: penalty += 15; details.append((f"乖离{dev:.0f}%严重", -15))
        elif dev > 20: penalty += 10; details.append((f"乖离{dev:.0f}%偏高", -10))
        elif dev > 15: penalty += 5

        # RSI超买
        if rsi14 > 80: penalty += 12; details.append((f"RSI{rsi14:.0f}过热", -12))
        elif rsi14 > 75: penalty += 8; details.append((f"RSI{rsi14:.0f}超买", -8))
        elif rsi14 > 70: penalty += 4

        # 缩量
        if vr_use < 0.3: penalty += 20; details.append((f"无量{vr_use:.1f}x", -20))
        elif vr_use < 0.5: penalty += 10; details.append((f"缩量{vr_use:.1f}x", -10))
        elif vr_use < 0.8: penalty += 3

        # 连涨透支
        if ind["chg_5d"] > 15: penalty += 10; details.append((f"5日+{ind['chg_5d']:.0f}%透支", -10))
        elif ind["chg_5d"] > 10: penalty += 5

        # 连涨天数
        if ind["up_days"] >= 5: penalty += 8; details.append((f"连涨{ind['up_days']}天", -8))
        elif ind["up_days"] >= 4: penalty += 4

        # 换手异常
        if turnover < 1: penalty += 10; details.append(("换手过低", -10))
        elif turnover > 25: penalty += 8; details.append((f"换手{int(turnover)}%过热", -8))

        # 量价背离惩罚
        if div_type == "bull_divergence":
            penalty += 15; details.append(("量价背离", -15))

        # 上影线+放量 = 出货
        us = cand["upper_shadow"]
        if us > 3:
            if vr_use > 1.5:
                penalty += min(10, int(us * 2)); details.append((f"放量上影{us:.1f}%出货", -min(10, int(us * 2))))
            else:
                penalty += min(5, int(us)); details.append((f"上影{us:.1f}%", -min(5, int(us))))

        # KDJ超买
        if ind["j"] > 100: penalty += 3; details.append((f"J={ind['j']:.0f}超买", -3))

        # 高价股
        if ind["cur"] > 80: penalty += 5; details.append((f"高价{ind['cur']:.0f}元", -5))

        score -= penalty
        score = max(0, min(100, score))

        # ATR止损
        stop_pct, stop_price = calc_atr_stop(ind["cur"], ind["atr14"])

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": cand["price"],
            "chg_today": cand["chg"], "prev": cand["prev"],
            "rsi14": rsi14, "rsi6": ind["rsi6"],
            "vr": vr_use, "chg_3d": ind["chg_3d"], "chg_5d": ind["chg_5d"],
            "dev": dev, "score": score, "details": details,
            "ma5": ind["ma5"], "ma10": ind["ma10"], "ma20": ind["ma20"], "ma60": ind["ma60"],
            "dif": ind["dif"], "dea": ind["dea"], "macdh": ind["macdh"],
            "k": ind["k"], "j": ind["j"],
            "upper_shadow": us, "amount": cand["amount"],
            "up_days": ind["up_days"],
            "turnover": turnover, "main_net": main_net,
            "rps": rps, "limit_up_count": lu,
            "div_type": div_type, "boll_pos": ind["boll_pos"],
            "ma5_slope": ind["ma5_slope"], "atr14": ind["atr14"],
            "stop_pct": stop_pct, "stop_price": stop_price,
        })
    except Exception as e:
        pass

results.sort(key=lambda x: x["score"], reverse=True)
print(f"    分析完成: {len(results)} 只")

# ===== Step 6: 补全名称 =====
print(f"\n  [6/6] 补充股票名称...")
missing = [r for r in results[:20] if not r["name"]]
if missing:
    names = get_name_batch([r["code"] for r in missing])
    for r in missing:
        r["name"] = names.get(r["code"], r["code"])

# ===== 输出 TOP15 =====
print(f"\n{'=' * 76}")
print(f"  动量策略 V3 TOP15  (大盘: {env_label})")
print(f"{'=' * 76}")

for i, r in enumerate(results[:15]):
    name_str = r["name"] or f"({r['code']})"
    bar_len = max(0, int(r["score"] / 5))
    bar = "\u2593" * bar_len + "\u2591" * (20 - bar_len)

    warnings = generate_risk_tags(r)

    if warnings:
        tag = "!!" if r["score"] < 60 else ("XX" if any("连涨" in w or "背离" in w or "无量" in w for w in warnings) else "??")
    else:
        tag = "OK" if r["score"] >= 75 else (".." if r["score"] >= 60 else "--")

    warn_str = " ".join(warnings) if warnings else "无风险"

    print(f"\n  #{i + 1} {name_str}({r['code']})  {r['price']:.2f}  今日{r['chg_today']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  RSI14={r['rsi14']:.0f}  量比={r['vr']:.1f}x  换手={r['turnover']:.1f}%  大单净量={r['main_net'] / 10000:.0f}万")
    print(f"  乖离={r['dev']:.1f}%  RPS={r['rps']:.0f}  涨停基因={r['limit_up_count']}次  风险: {warn_str}")
    print(f"  MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f}  KDJ-J={r['j']:.0f}  BOLL位置={r['boll_pos']:.0f}%")
    print(f"  MA5={r['ma5']:.2f} MA10={r['ma10']:.2f} MA20={r['ma20']:.2f} MA60={r['ma60']:.2f}")

# ===== 最终推荐 =====
if results:
    # V3 安全门
    safe = [r for r in results
            if r["vr"] >= 0.6
            and r["rsi14"] <= 72
            and r.get("dev", 0) <= 18
            and r["chg_5d"] <= 10
            and r["turnover"] >= 1
            and r["turnover"] <= 20
            and r.get("div_type") != "bull_divergence"
            and r["up_days"] < 4
            and r["j"] < 105
            and r["upper_shadow"] < 4]
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]

    risk_flags = []
    if best["vr"] < 0.3: risk_flags.append("低流动性")
    if best.get("dev", 0) > 20: risk_flags.append("乖离过大")
    if best["rsi14"] > 72: risk_flags.append("RSI超买")
    if best["chg_5d"] > 12: risk_flags.append("5日透支")
    if best["up_days"] >= 4: risk_flags.append(f"连涨{best['up_days']}天")
    if best["j"] > 105: risk_flags.append("KDJ超买")
    if best["turnover"] < 1: risk_flags.append("换手过低")
    if best.get("div_type") == "bull_divergence": risk_flags.append("量价背离")

    score_threshold = 75 if market_score >= 0 else 80

    print(f"\n{'=' * 76}")
    print(f"  最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'=' * 76}")
    print(f"\n  现价: {best['price']:.2f}    今日涨幅: {best['chg_today']:+.1f}%")
    print(f"  大盘: {env_label}    换手率: {best['turnover']:.1f}%")
    print(f"  大单净量: {best['main_net'] / 10000:.0f}万    RPS: {best['rps']:.0f}")

    if market_score <= -2:
        print(f"\n  !! 大盘环境极弱（涨{up_ratio:.0f}%跌{down_ratio:.0f}%），不建议买入。空仓等待。")
    elif risk_flags:
        print(f"\n  !! 风险: {', '.join(risk_flags)} - 不推荐买入")
        print(f"  今日市场不适合动量策略，建议空仓等待")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 今日尾盘直接买入")
        print(f"  目标: {best['price'] * 1.04:.2f}(+4%) ~ {best['price'] * 1.05:.2f}(+5%)")
        print(f"  ATR止损: {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
        print(f"  卖出: 明天盘中达标即卖")
        print(f"  仓位: <= 25%")
    elif best["score"] >= 65:
        print(f"\n  !! 评分 {best['score']}/100 勉强可关注但不建议重仓")
        print(f"  如果要做: 仓位 <= 10%, ATR止损 {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
    else:
        print(f"\n  !! 评分不足 {best['score']}/100，不建议买入。等更好的机会。")

print(f"\n  !! 以上为技术面分析，不构成投资建议")
