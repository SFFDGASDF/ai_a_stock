"""
超跌反弹策略 V3 — 今天大跌 明天反弹（全面升级版）
新增换手率、大单净量抄底信号、量价背离、BOLL位置、ATR止损
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
    get_name_batch, generate_risk_tags,
    UA,
)
import requests

client = get_client()

print("=" * 72)
print("  超跌反弹策略 V3 — 今天大跌  明天反弹（全面升级）")
print("=" * 72)

# ===== Step 1: 获取股票列表 =====
print("\n  [1/6] 获取沪深A股列表...")
all_codes = get_stock_list()
name_map = dict(all_codes)
codes = [c for c, _ in all_codes]
print(f"    共 {len(codes)} 只")

# ===== Step 2: 大盘环境检测 =====
print("\n  [2/6] 大盘环境检测...")
env_label, market_score, up_ratio, down_ratio, index_status = get_market_env(codes[:500])
print(f"    {env_label}  涨:{up_ratio:.0f}%  跌:{down_ratio:.0f}%")

# ===== Step 3: 行情扫描 (跌幅 2-8%) =====
print(f"\n  [3/6] 行情扫描 (找今日大跌)...")
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
        print(f"    进度: {min(i + batch_size, len(codes))}/{len(codes)}, 候选 {len(candidates)}")

# 按 (下影线 + 超跌程度) 排序取前80
candidates.sort(key=lambda x: x["lower_shadow"] * 1.5 - abs(x["chg"]) / 8, reverse=True)
candidates = candidates[:80]
print(f"    今日跌2-8%+非ST+>3000万: {len(candidates)} 只")

# ===== Step 4: 换手率+资金流向 =====
print(f"\n  [4/6] 获取换手率+大单净量...")
candidate_codes = [c["code"] for c in candidates]
extra_data = get_extra_data_batch(candidate_codes)
print(f"    获取到 {len(extra_data)} 只额外数据")

# ===== Step 5: 技术面深度分析 =====
print(f"\n  [5/6] 技术面深度分析...")
results = []

for idx, c in enumerate(candidates):
    code = c["code"]
    try:
        bars = client.bars(symbol=code, category=4, offset=120)
        if bars is None or len(bars) < 30:
            continue

        df = bars.copy()
        ind = calc_technical_indicators(df)

        # 额外数据
        extra = extra_data.get(code, {})
        turnover = extra.get("turnover", 5)
        main_net = extra.get("main_net", 0)

        # 量价背离检测（超跌语境：跌+放量+下影=资金抄底）
        close_s = df["close"].astype(float)
        vol_s = df["vol"].astype(float)
        div_type, div_penalty = detect_volume_price_divergence(close_s, vol_s, 5)

        # 支撑
        nearest_support = "无"
        support_dist = 99
        for label, ma_val in [("MA20", ind["ma20"]), ("MA60", ind["ma60"])]:
            if ma_val > 0 and ind["cur"] > ma_val:
                d = (ind["cur"] / ma_val - 1) * 100
                if d < support_dist:
                    support_dist = d
                    nearest_support = label

        # ======================
        # 评分系统 V3 (满分100)
        # ======================
        score = 0
        details = []
        penalty = 0
        chg_abs = abs(c["chg"])
        ls = c["lower_shadow"]

        # 1. 超跌深度 (max 18)
        if 5 <= chg_abs <= 7:
            score += 18; details.append(("跌5-7%黄金坑", 18))
        elif 4 <= chg_abs < 5:
            score += 15; details.append((f"跌{chg_abs:.0f}%", 15))
        elif 7 <= chg_abs < 8:
            score += 14; details.append(("跌7-8%", 14))
        else:
            score += 11; details.append((f"跌{chg_abs:.0f}%", 11))

        # 2. 下影线 (max 15)
        if ls > 3:
            score += 15; details.append((f"长下影{ls:.1f}%", 15))
        elif ls > 1.5:
            score += 11; details.append((f"下影{ls:.1f}%", 11))
        elif ls > 0.5:
            score += 7; details.append((f"短下影{ls:.1f}%", 7))
        else:
            score += 2

        # 3. 均线支撑 (max 14)
        if ind["cur"] > ind["ma5"] > ind["ma10"] > ind["ma20"]:
            if ind["dev"] <= 12:
                score += 14; details.append(("多头+乖离安全", 14))
            elif ind["dev"] <= 20:
                score += 9; details.append((f"多头(乖离{ind['dev']:.0f}%)", 9))
            else:
                score += 4
        elif nearest_support != "无" and support_dist < 3:
            score += 12; details.append((f"{nearest_support}支撑({support_dist:.1f}%)", 12))
        elif nearest_support != "无" and support_dist < 6:
            score += 8; details.append((f"{nearest_support}附近", 8))
        elif ind["cur"] > ind["ma20"]:
            score += 5; details.append(("MA20上方", 5))
        elif ind["cur"] > ind["ma60"]:
            score += 3
        else:
            score += 1

        # 4. RSI (max 10)
        rsi6 = ind["rsi6"]
        if rsi6 < 25:
            score += 10; details.append((f"RSI{rsi6:.0f}极超卖", 10))
        elif rsi6 < 35:
            score += 8; details.append((f"RSI{rsi6:.0f}超卖", 8))
        elif rsi6 < 45:
            score += 6; details.append((f"RSI{rsi6:.0f}偏低", 6))
        else:
            score += 3

        # 5. MACD (max 8)
        if ind["dif"] > ind["dea"] and ind["dif"] > 0:
            score += 8; details.append(("MACD多头", 8))
        elif ind["dif"] > ind["dea"]:
            score += 6; details.append(("MACD金叉", 6))
        elif ind["dif"] > ind["dea"] - 0.05:
            score += 4; details.append(("MACD将金叉", 4))
        else:
            score += 1

        # 6. 量能 (max 8)
        vr_use = ind["vr"]
        if 1.2 <= vr_use <= 2.5:
            score += 8; details.append((f"放量{vr_use:.1f}x", 8))
        elif 0.8 <= vr_use <= 1.2:
            score += 5; details.append((f"量{vr_use:.1f}x", 5))
        elif vr_use > 2.5:
            score += 3; details.append(("巨量", 3))

        # 7. BOLL位置 (max 6)
        bp = ind["boll_pos"]
        if bp < 15:
            score += 6; details.append((f"BOLL{bp:.0f}%触底", 6))
        elif bp < 30:
            score += 4; details.append((f"BOLL{bp:.0f}%低位", 4))
        elif bp < 50:
            score += 2

        # 8. 换手率 (max 6)
        if turnover >= 1.5:
            score += 6; details.append((f"换手{turnover:.1f}%有人接", 6))
        elif turnover >= 0.8:
            score += 3
        else:
            score += 1

        # 9. 大单净量 (max 8)
        if main_net > 5000000:
            score += 8; details.append(("主力抄底", 8))
        elif main_net > 0:
            score += 5; details.append(("主力微流入", 5))
        elif main_net > -3000000:
            score += 2

        # 10. 量价背离+下影=资金抄底 (max 10)
        if div_type == "bear_divergence" and ls > 1.5:
            score += 10; details.append(("放量下影抄底", 10))
        elif div_type == "bear_divergence":
            score += 6; details.append(("放量企稳", 6))
        elif ls > 3 and ind["vr"] > 0.8:
            score += 5; details.append(("下影企稳", 5))

        # 11. 连阴反弹概率 (max 5)
        dd = ind["down_days"]
        if 3 <= dd <= 4:
            score += 5; details.append((f"连阴{dd}天反弹概率高", 5))
        elif dd == 2:
            score += 3

        # --- 惩罚系统 ---
        # 高位补跌
        dev = ind["dev"]
        if dev > 30: penalty += 20; details.append((f"崩盘乖离{dev:.0f}%", -20))
        elif dev > 25: penalty += 15; details.append((f"乖离{dev:.0f}%严重", -15))
        elif dev > 18: penalty += 8; details.append((f"乖离{dev:.0f}%偏高", -8))

        # 假超跌
        if rsi6 > 65: penalty += 12; details.append((f"RSI{rsi6:.0f}假超跌", -12))
        elif rsi6 > 55: penalty += 5

        # 无量
        if ind["vr"] < 0.3: penalty += 20; details.append(("无量无人交易", -20))
        elif ind["vr"] < 0.5: penalty += 10; details.append(("缩量流动性差", -10))
        elif ind["vr"] < 0.8: penalty += 3

        # 获利盘
        if ind["chg_5d"] > 15: penalty += 8; details.append((f"5日+{ind['chg_5d']:.0f}%追高", -8))
        elif ind["chg_5d"] > 10: penalty += 5

        # 连续下跌
        if ind["chg_5d"] < -10: penalty += 8; details.append((f"5日{ind['chg_5d']:.0f}%连跌", -8))

        # 连阴天数
        if dd >= 5: penalty += 6 + (dd - 5) * 3; details.append((f"连阴{dd}天", -6 - (dd - 5) * 3))
        elif dd >= 4: penalty += 8; details.append((f"连阴{dd}天", -8))
        elif dd >= 3: penalty += 4

        # 换手异常
        if turnover < 1: penalty += 10; details.append(("换手过低", -10))

        # 大单持续流出
        if main_net < -10000000: penalty += 10; details.append(("主力大幅流出", -10))
        elif main_net < -5000000: penalty += 5; details.append(("主力流出", -5))

        # 高价
        if ind["cur"] > 80: penalty += 5

        # 振幅过大
        if c["amplitude"] > 8: penalty += 2

        score -= penalty

        # 反弹潜力 = 超跌幅度 x 放量 x 下影 / 连阴
        bounce_potential = chg_abs * max(0.5, ind["vr"]) * max(1, ls) / max(1, dd)

        # ATR止损
        stop_pct, stop_price = calc_atr_stop(ind["cur"], ind["atr14"])

        name = name_map.get(code, "")
        results.append({
            "code": code, "name": name, "price": ind["cur"], "chg": c["chg"],
            "lower_shadow": ls, "amplitude": c["amplitude"],
            "amount": c["amount"], "rsi6": rsi6, "rsi14": ind["rsi14"],
            "dif": ind["dif"], "dea": ind["dea"], "macdh": ind["macdh"],
            "kdj_j": ind["j"], "vr": ind["vr"], "chg_5d": ind["chg_5d"],
            "ma5": ind["ma5"], "ma10": ind["ma10"], "ma20": ind["ma20"], "ma60": ind["ma60"],
            "support": nearest_support, "support_dist": support_dist,
            "boll_pos": ind["boll_pos"], "dev": ind["dev"],
            "score": score, "details": details,
            "down_days": dd, "turnover": turnover,
            "main_net": main_net, "div_type": div_type,
            "bounce_potential": bounce_potential,
            "stop_pct": stop_pct, "stop_price": stop_price,
        })
    except:
        pass

results.sort(key=lambda x: x["score"], reverse=True)

# ===== Step 6: 补全名称 =====
print(f"\n  [6/6] 补充股票名称...")
missing = [r for r in results[:20] if not r["name"]]
if missing:
    names = get_name_batch([r["code"] for r in missing])
    for r in missing:
        r["name"] = names.get(r["code"], r["code"])

# ===== 输出 TOP15 =====
print(f"\n{'=' * 72}")
print(f"  超跌反弹 V3 TOP15  (大盘: {env_label})")
print(f"{'=' * 72}")

for i, r in enumerate(results[:15]):
    name_str = r["name"] or f"({r['code']})"
    bar_len = max(0, int(r["score"] / 5))
    bar = "\u2593" * bar_len + "\u2591" * (20 - bar_len)

    warnings = generate_risk_tags(r)

    if warnings:
        tag = "!!" if r["score"] < 55 else ("??" if any("连阴" in w or "假超跌" in w or "无量" in w for w in warnings) else "XX")
    else:
        tag = "OK" if r["score"] >= 75 else (".." if r["score"] >= 60 else "--")

    warn_str = " ".join(warnings) if warnings else "无风险信号"

    print(f"\n  #{i + 1} {name_str}({r['code']})  {r['price']:.2f}  今日{r['chg']:+.1f}%  评分{r['score']}  {tag}")
    print(f"  [{bar}]")
    print(f"  RSI6={r['rsi6']:.0f}  量比={r['vr']:.1f}x  换手={r['turnover']:.1f}%  大单={r['main_net'] / 10000:.0f}万")
    print(f"  下影={r['lower_shadow']:.1f}%  反弹潜力={r['bounce_potential']:.1f}  连阴={r['down_days']}天  风险: {warn_str}")
    print(f"  BOLL={r['boll_pos']:.0f}%  支撑={r['support']}({r['support_dist']:.1f}%)  KDJ-J={r['kdj_j']:.0f}")
    print(f"  MA5={r['ma5']:.2f}  MA20={r['ma20']:.2f}  MA60={r['ma60']:.2f}  MACD DIF={r['dif']:.3f} DEA={r['dea']:.3f}")

# ===== 最终推荐 =====
if results:
    safe = [r for r in results
            if r["vr"] >= 0.5
            and r["rsi6"] <= 65
            and r.get("dev", 0) <= 25
            and r["chg_5d"] > -12
            and r["down_days"] < 5
            and r["turnover"] >= 0.6]
    best = safe[0] if safe else results[0]
    best_name = best["name"] or best["code"]

    risk_flags = []
    if best["vr"] < 0.3: risk_flags.append("低流动性")
    if best.get("dev", 0) > 25: risk_flags.append("高位崩盘")
    if best["rsi6"] > 65: risk_flags.append("假超跌")
    if best["chg_5d"] < -12: risk_flags.append("持续下跌")
    if best["down_days"] >= 5: risk_flags.append(f"连阴{best['down_days']}天")
    if best["turnover"] < 0.6: risk_flags.append("无人关注")

    score_threshold = 72 if market_score >= -1 else 80

    print(f"\n{'=' * 72}")
    print(f"  最终推荐: {best_name}({best['code']})  {best['score']}/100")
    print(f"{'=' * 72}")
    print(f"\n  现价: {best['price']:.2f}    今日跌幅: {best['chg']:.1f}%")
    print(f"  大盘: {env_label}    换手率: {best['turnover']:.1f}%")
    print(f"  大单净量: {best['main_net'] / 10000:.0f}万    反弹潜力: {best['bounce_potential']:.1f}")

    if market_score <= -2:
        print(f"\n  !! 大盘环境极弱，超跌策略风险极高，不建议买入")
    elif risk_flags:
        print(f"\n  !! 风险: {', '.join(risk_flags)} - 不推荐买入")
    elif best["score"] >= score_threshold:
        print(f"\n  买入: 今日尾盘 / 明早低开")
        print(f"  目标: {best['price'] * 1.04:.2f}(+4%) ~ {best['price'] * 1.05:.2f}(+5%)")
        print(f"  ATR止损: {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
        print(f"\n  !! 超跌反弹风险高于顺势交易，控制仓位 <= 20%")
    elif best["score"] >= 60:
        print(f"\n  !! 评分 {best['score']}/100 勉强可关注但不重仓")
        print(f"  仓位 <= 10%, ATR止损 {best['stop_price']:.2f}({best['stop_pct']:.1f}%)")
    else:
        print(f"\n  !! 评分不足 {best['score']}/100，不建议买入")

print(f"\n  !! 以上为技术分析，不构成投资建议")
