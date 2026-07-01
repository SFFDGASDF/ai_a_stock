"""
均线突破策略 V1 — T+1 短线（全新策略）
捕捉股价放量突破MA20/MA60关键均线 + 主力资金共振的启动信号
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
print("  均线突破策略 V1 — 放量突破+资金共振（全新策略）")
print("=" * 78)

# ===== Step 0: 市场情绪 =====
print("\n  [0/7] 市场情绪检测...")
sentiment = get_limit_up_sentiment()
print(f"    涨停{sentiment['limit_up_count']}家  炸板率{sentiment['broken_rate']:.0f}%  温度{sentiment['sentiment_score']:.0f}  {sentiment['sentiment_label']}")

if sentiment["broken_rate"] > 35:
    print(f"  ❌ 炸板率{sentiment['broken_rate']:.0f}%>35%，不操作")
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

# ===== Step 3: 突破扫描（V1新增逻辑）=====
print(f"\n  [3/7] 突破扫描 (找今日突破MA20/MA60的股票)...")

# 先取行情
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
            if price < 3 or amount < 20000000:
                continue

            chg_pct = (price / prev - 1) * 100
            # 突破策略：涨幅0.5-6%（不追涨停），成交额>2000万
            if 0.5 <= chg_pct <= 6:
                is_20cm = code.startswith("30") or code.startswith("68")
                is_limit_up = chg_pct >= (19.5 if is_20cm else 9.5)
                if is_limit_up:
                    continue
                upper_shadow = max(0, (high - max(price, open_p)) / open_p * 100) if open_p > 0 else 0
                candidates.append({
                    "code": code, "price": price, "prev": prev,
                    "open": open_p, "high": high, "low": low,
                    "chg": chg_pct, "amount": amount, "vol": vol,
                    "upper_shadow": upper_shadow,
                })
    except:
        pass
    if (i // batch_size + 1) % 15 == 0:
        print(f"    进度: {min(i + batch_size, len(codes))}/{len(codes)}, 候选 {len(candidates)}")

candidates.sort(key=lambda x: x["amount"], reverse=True)
candidates = candidates[:200]
print(f"    初筛候选(涨幅0.5-6%, >2000万): {len(candidates)} 只")

# ===== Step 4: 数据获取 =====
print(f"\n  [4/7] 获取换手率+资金+基本面...")
candidate_codes = [c["code"] for c in candidates]
extra_data = get_extra_data_batch(candidate_codes)
fund_data = get_fundamental_data_batch(candidate_codes)
print(f"    数据: 换手{len(extra_data)}只  基本面{len(fund_data)}只")

# ===== Step 5: 技术面深度分析 =====
print(f"\n  [5/7] 技术面深度分析...")
global_chg20 = []
for ci in range(0, min(500, len(codes)), 80):
    batch = codes[ci:ci + 80]
    try:
        quotes = client.quotes(symbol=batch)
        if quotes is None or len(quotes) == 0:
            continue
        for _, q in quotes.iterrows():
            price = float(q.get("price", 0) or 0)
            prev_close = float(q.get("last_close", 0) or 0)
            if price > 0 and prev_close > 0:
                global_chg20.append((price / prev_close - 1) * 100)
    except:
        pass

results = []

for idx, cand in enumerate(candidates):
    code = cand["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 60:
            continue

        df = bars.copy()
        ind = calc_technical_indicators(df)

        # 突破条件判断
        # 昨日在MA20/MA60之下，今日在之上
        close_hist = df["close"].astype(float)
        yesterday = float(close_hist.iloc[-2])
        ma20_yesterday = float(close_hist.rolling(20).mean().iloc[-2])

        # 突破类型
        breakout_ma20 = yesterday < ma20_yesterday and ind["cur"] > ind["ma20"]
        breakout_ma60 = ind["ma60"] > 0 and yesterday < ind["ma60"] and ind["cur"] > ind["ma60"]

        if not (breakout_ma20 or breakout_ma60):
            continue

        extra = extra_data.get(code, {})
        turnover = extra.get("turnover", 0)
        main_net = extra.get("main_net", 0)

        # 放量确认：量比>1.2
        if ind["vr"] < 1.2:
            continue

        # === 基本面过滤 ===
        fund = fund_data.get(code, {})
        pe = fund.get("pe", 0)
        pb = fund.get("pb", 0)
        total_mv = fund.get("total_mv", 0)

        if pe < 0 or pe > 200:
            continue
        if 0 < total_mv < 2_000_000_000:
            continue

        # === 真实RPS ===
        rps20, rps60 = calc_true_rps(code, ind["chg_20d"], None, global_chg20, None)

        # 量价背离
        close_s = df["close"].astype(float)
        vol_s = df["vol"].astype(float)
        div_type, div_penalty = detect_volume_price_divergence(close_s, vol_s, 5)

        # 高位放量
        high_vol_danger = ind["boll_pos"] > 85 and ind["vr"] > 1.5

        # ======================
        # 评分系统 (满分100)
        # ======================
        score = 0
        details = []
        penalty = 0

        # 1. 突破强度 (max 18)
        breakout_score = 0
        if breakout_ma20 and breakout_ma60:
            breakout_score += 12; details.append(("同时突破MA20+MA60", 12))
        elif breakout_ma20:
            breakout_score += 8; details.append(("突破MA20", 8))
        elif breakout_ma60:
            breakout_score += 6; details.append(("突破MA60", 6))

        # 突破幅度
        dev_to_ma20 = (ind["cur"] / ind["ma20"] - 1) * 100 if ind["ma20"] > 0 else 0
        if dev_to_ma20 > 3:
            breakout_score += 6; details.append(("强势突破", 6))
        elif dev_to_ma20 > 1:
            breakout_score += 4
        score += min(18, breakout_score)

        # 2. 量能确认 (max 18)
        vol_score = 0
        if 1.5 <= ind["vr"] <= 3.0:
            vol_score += 10; details.append((f"放量{ind['vr']:.1f}x突破", 10))
        elif 1.2 <= ind["vr"] < 1.5:
            vol_score += 7; details.append((f"温和放量{ind['vr']:.1f}x", 7))

        if 3 <= turnover <= 12:
            vol_score += 8; details.append((f"换手{turnover:.1f}%活跃", 8))
        elif 2 <= turnover < 3:
            vol_score += 4
        score += min(18, vol_score)

        # 3. 资金共振 (max 15)
        if main_net > 10000000:
            score += 15; details.append(("主力大幅流入", 15))
        elif main_net > 5000000:
            score += 12; details.append(("主力流入", 12))
        elif main_net > 1000000:
            score += 8; details.append(("主力微流入", 8))
        elif main_net > 0:
            score += 4
        else:
            score += 1

        # 4. 趋势位置 (max 12)
        pos_score = 0
        if ind["cur"] > ind["ma5"] > ind["ma10"]:
            pos_score += 6; details.append(("短均多头", 6))
        if ind["boll_pos"] < 75:
            pos_score += 3  # 突破位置适中
        if ind["ma5_slope"] > 0:
            pos_score += 3; details.append(("MA5拐头", 3))
        score += min(12, pos_score)

        # 5. RPS强度 (max 10)
        if rps20 >= 80:
            score += 10; details.append((f"RPS{rps20:.0f}极强", 10))
        elif rps20 >= 65:
            score += 8; details.append((f"RPS{rps20:.0f}强势", 8))
        elif rps20 >= 50:
            score += 5
        else:
            score += 2

        # 6. 行业热度 (max 8)
        if main_net > 10000000:
            score += 6
        if rps20 > 60:
            score += 2

        # 7. 基本面 (max 7)
        fund_score = 0
        if 5 < pe < 40:
            fund_score += 4; details.append(("PE合理", 4))
        if 1 < pb < 4:
            fund_score += 3; details.append(("PB合理", 3))
        score += min(7, fund_score)

        # 8. 涨停基因 (max 6)
        lu = ind["limit_up_count"]
        if lu >= 3:
            score += 6; details.append((f"涨停{lu}次活跃", 6))
        elif lu >= 1:
            score += 3

        # 9. 技术形态 (max 6)
        tech_score = 0
        if ind["dif"] > ind["dea"] and ind["dif"] > 0:
            tech_score += 4; details.append(("MACD金叉", 4))
        if 55 <= ind["rsi14"] <= 72:
            tech_score += 2; details.append((f"RSI{ind['rsi14']:.0f}", 2))
        score += min(6, tech_score)

        # --- 惩罚 ---
        dev = ind["dev"]
        if dev > 25: penalty += 10; details.append((f"乖离{dev:.0f}%", -10))
        if high_vol_danger: penalty += 8; details.append(("高位放量", -8))
        if ind["up_days"] >= 5: penalty += 6; details.append((f"连涨{ind['up_days']}天", -6))
        if div_type == "bull_divergence": penalty += 10; details.append(("量价背离", -10))
        if turnover > 25: penalty += 5
        if main_net < -5000000: penalty += 5
        if ind["j"] > 105: penalty += 3
        if cand["upper_shadow"] > 4: penalty += 3
        if rps20 < 30: penalty += 4

        score -= penalty
        score = max(0, min(100, score))

        stop_pct, stop_price = calc_atr_stop(ind["cur"], ind["atr14"])

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": cand["price"],
            "chg_today": cand["chg"],
            "rsi14": ind["rsi14"], "vr": ind["vr"],
            "turnover": turnover, "main_net": main_net,
            "score": score, "details": details,
            "ma5": ind["ma5"], "ma10": ind["ma10"], "ma20": ind["ma20"],
            "ma60": ind["ma60"],
            "dev": dev, "boll_pos": ind["boll_pos"],
            "dif": ind["dif"], "dea": ind["dea"],
            "up_days": ind["up_days"], "limit_up_count": lu,
            "ma5_slope": ind["ma5_slope"],
            "j": ind["j"], "upper_shadow": cand["upper_shadow"],
            "amount": cand["amount"],
            "stop_pct": stop_pct, "stop_price": stop_price,
            "rps20": rps20, "pe": pe, "pb": pb, "total_mv": total_mv,
            "breakout_ma20": breakout_ma20, "breakout_ma60": breakout_ma60,
        })
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)
print(f"    分析完成: {len(results)} 只确认突破")

# ===== Step 6: 补全名称 =====
print(f"\n  [6/7] 补充股票名称...")
missing = [r for r in results[:20] if not r["name"]]
if missing:
    names = get_name_batch([r["code"] for r in missing])
    for r in missing:
        r["name"] = names.get(r["code"], r["code"])

# ===== 输出 TOP15 =====
print(f"\n{'=' * 78}")
print(f"  均线突破策略 TOP15  (大盘: {env_label}  情绪: {sentiment['sentiment_label']})")
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
    bk = "MA20" if r.get("breakout_ma20") else ""
    bk += "+MA60" if r.get("breakout_ma60") else ""
    pe_str = f"PE={r.get('pe', 0):.1f}" if r.get("pe", 0) > 0 else ""

    print(f"\n  #{i + 1} {name_str}({r['code']})  {r['price']:.2f}  今日{r['chg_today']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  突破: {bk}  量比={r['vr']:.1f}x  换手={r['turnover']:.1f}%  大单={r['main_net'] / 10000:.0f}万")
    print(f"  RPS20={r['rps20']:.0f}  BOLL={r['boll_pos']:.0f}%  {pe_str}  风险: {warn_str}")
    print(f"  MA5={r['ma5']:.2f}  MA20={r['ma20']:.2f}  MA60={r['ma60']:.2f}  MACD DIF={r['dif']:.3f}")

# ===== 最终推荐 =====
if results:
    safe = [r for r in results
            if r["vr"] >= 1.2
            and r["dev"] <= 18
            and r["up_days"] < 4
            and r["main_net"] > -3000000
            and r["upper_shadow"] < 4
            and r.get("rps20", 50) >= 35]
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]

    score_threshold = 70 if market_score >= 0 else 78

    print(f"\n{'=' * 78}")
    print(f"  最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'=' * 78}")
    print(f"\n  现价: {best['price']:.2f}    今日涨幅: {best['chg_today']:+.1f}%")
    print(f"  大盘: {env_label}    情绪: {sentiment['sentiment_label']}")
    print(f"  量比: {best['vr']:.1f}x  换手: {best['turnover']:.1f}%  大单: {best['main_net'] / 10000:.0f}万")
    print(f"  RPS20: {best['rps20']:.0f}    PE: {best.get('pe', 0):.1f}")
    bk = "MA20" if best.get("breakout_ma20") else ""
    bk += "+MA60" if best.get("breakout_ma60") else ""
    print(f"  突破: {bk}    ATR止损: {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")

    if market_score <= -2:
        print(f"\n  !! 大盘极弱，不建议操作")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 尾盘确认突破有效(不回落)后买入")
        print(f"  目标: {best['price'] * 1.04:.2f}(+4%) ~ {best['price'] * 1.06:.2f}(+6%)")
        print(f"  ATR止损: {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
        print(f"  仓位: 总资金20%, 单票10%")
    elif best["score"] >= 60:
        print(f"\n  !! 评分 {best['score']}/100 勉强可关注")
        print(f"  仓位 <= 8%")
    else:
        print(f"\n  !! 评分不足，不建议买入")

print(f"\n  !! 以上为技术分析，不构成投资建议")
