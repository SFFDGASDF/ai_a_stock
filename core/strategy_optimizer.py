"""
策略优化器 — 因子IC分析 + 权重自动调整 + 网格搜索
基于历史选股绩效数据，不断优化各策略因子权重，提高准确率
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime
import core.db_manager as db_manager
import core.performance_tracker as performance_tracker


# ============================================================
#  各策略因子定义
# ============================================================

FACTOR_CONFIGS = {
    "momentum": {
        "rewards": [
            {"name": "均线排列",   "db_col": "score",     "weight": 14, "type": "trend"},
            {"name": "RSI健康",    "db_col": "rsi14",      "weight": 10, "type": "momentum"},
            {"name": "MACD多头",   "db_col": "dif",        "weight": 10, "type": "trend"},
            {"name": "量能放大",   "db_col": "vr",         "weight": 10, "type": "volume"},
            {"name": "乖离适中",   "db_col": "dev",        "weight": 5,  "type": "position"},
            {"name": "涨幅温和",   "db_col": "chg_today",  "weight": 4,  "type": "momentum"},
            {"name": "换手健康",   "db_col": "turnover",   "weight": 8,  "type": "volume"},
            {"name": "量价配合",   "db_col": "vr",         "weight": 10, "type": "volume"},
            {"name": "主力流入",   "db_col": "main_net",   "weight": 8,  "type": "capital"},
            {"name": "RPS强势",    "db_col": "rps20",      "weight": 8,  "type": "strength"},
            {"name": "涨停基因",   "db_col": "limit_up_count", "weight": 4, "type": "activity"},
            {"name": "行业动量",   "db_col": "rps20",      "weight": 3,  "type": "strength"},
            {"name": "基本面质量", "db_col": "pe",         "weight": 4,  "type": "fundamental"},
        ],
    },
    "oversold": {
        "rewards": [
            {"name": "超跌深度",   "db_col": "chg_today",  "weight": 18, "type": "position"},
            {"name": "下影线",     "db_col": "lower_shadow","weight": 15, "type": "candle"},
            {"name": "均线支撑",   "db_col": "score",      "weight": 14, "type": "trend"},
            {"name": "RSI超卖",    "db_col": "rsi6",       "weight": 10, "type": "momentum"},
            {"name": "MACD企稳",   "db_col": "dif",        "weight": 8,  "type": "trend"},
            {"name": "量能反弹",   "db_col": "vr",         "weight": 8,  "type": "volume"},
            {"name": "BOLL触底",   "db_col": "boll_pos",   "weight": 6,  "type": "position"},
            {"name": "换手有人接", "db_col": "turnover",   "weight": 6,  "type": "volume"},
            {"name": "主力抄底",   "db_col": "main_net",   "weight": 8,  "type": "capital"},
            {"name": "低位放量",   "db_col": "vr",         "weight": 10, "type": "volume"},
            {"name": "连阴反弹",   "db_col": "down_days",  "weight": 5,  "type": "activity"},
        ],
    },
    "volume_price": {
        "rewards": [
            {"name": "量价配合",   "db_col": "vr",         "weight": 18, "type": "volume"},
            {"name": "资金共振",   "db_col": "main_net",   "weight": 16, "type": "capital"},
            {"name": "趋势强度",   "db_col": "score",      "weight": 16, "type": "trend"},
            {"name": "换手健康",   "db_col": "turnover",   "weight": 10, "type": "volume"},
            {"name": "RPS强势",    "db_col": "rps20",      "weight": 10, "type": "strength"},
            {"name": "位置适中",   "db_col": "boll_pos",   "weight": 8,  "type": "position"},
            {"name": "涨停基因",   "db_col": "limit_up_count","weight": 5, "type": "activity"},
            {"name": "行业热度",   "db_col": "main_net",   "weight": 4,  "type": "capital"},
            {"name": "基本面质量", "db_col": "pe",         "weight": 3,  "type": "fundamental"},
        ],
    },
    "breakout": {
        "rewards": [
            {"name": "突破强度",   "db_col": "score",      "weight": 18, "type": "trend"},
            {"name": "量能确认",   "db_col": "vr",         "weight": 18, "type": "volume"},
            {"name": "资金共振",   "db_col": "main_net",   "weight": 15, "type": "capital"},
            {"name": "趋势位置",   "db_col": "boll_pos",   "weight": 12, "type": "position"},
            {"name": "RPS强度",    "db_col": "rps20",      "weight": 10, "type": "strength"},
            {"name": "行业热度",   "db_col": "rps20",      "weight": 8,  "type": "strength"},
            {"name": "基本面质量", "db_col": "pe",         "weight": 7,  "type": "fundamental"},
            {"name": "涨停基因",   "db_col": "limit_up_count","weight": 6, "type": "activity"},
            {"name": "技术形态",   "db_col": "dif",        "weight": 6,  "type": "trend"},
        ],
    },
}


# ============================================================
#  IC 分析
# ============================================================

def compute_ic_analysis(strategy_key):
    """计算因子 IC，返回按 |IC| 排序的因子列表"""
    ic_data = db_manager.get_ic_analysis(strategy_key)
    return ic_data


# ============================================================
#  优化方法 1: IC 缩放
# ============================================================

def optimize_by_ic(strategy_key, learning_rate=0.1):
    """
    基于 IC 值缩放权重:
    - IC > 0.03  → 权重 × (1 + learning_rate)
    - IC < -0.01 → 权重 × (1 - learning_rate)
    - IC ≈ 0     → 权重不变
    - 每次调整幅度限制在 ±30%
    """
    config = FACTOR_CONFIGS.get(strategy_key)
    if not config:
        return {"error": f"未知策略: {strategy_key}"}

    ic_data = compute_ic_analysis(strategy_key)
    if not ic_data:
        return {"error": f"策略 {strategy_key} 数据不足，需要至少 10 条有绩效的 picks"}

    # 建立因子名到 IC 的映射
    ic_map = {item["factor"]: item["ic_1d"] for item in ic_data}

    weights_list = []
    changes = []

    for factor in config["rewards"]:
        db_col = factor["db_col"]
        original_w = factor["weight"]
        ic_val = ic_map.get(db_col, 0)

        # IC 缩放
        if abs(ic_val) > 0.05:
            adj = 1.0 + learning_rate * np.sign(ic_val) * min(abs(ic_val) * 2, 0.3)
        elif abs(ic_val) > 0.02:
            adj = 1.0 + learning_rate * np.sign(ic_val) * min(abs(ic_val) * 1.5, 0.2)
        elif abs(ic_val) > 0.01:
            adj = 1.0 + learning_rate * np.sign(ic_val) * 0.1
        else:
            adj = 1.0  # IC ≈ 0, 不调整

        # 限制调整范围
        adj = max(0.7, min(1.3, adj))
        new_w = round(original_w * adj, 1)
        new_w = max(1, min(30, new_w))  # 权重范围 [1, 30]

        changes.append({
            "factor": factor["name"],
            "original": original_w,
            "new": new_w,
            "ic": round(ic_val, 4),
            "adj": round(adj, 2),
        })

        weights_list.append({
            "factor_name": factor["name"],
            "factor_type": "reward",
            "original_weight": original_w,
            "current_weight": original_w,
            "optimized_weight": new_w,
            "ic_value": round(ic_val, 4),
            "confidence": min(1.0, abs(ic_val) * 10),
            "sample_count": len([x for x in ic_data if x["factor"] == db_col]),
        })

    # 保存到数据库
    db_manager.save_factor_weights(strategy_key, weights_list)

    # 记录优化日志
    avg_ic = np.mean([abs(c["ic"]) for c in changes]) if changes else 0
    db_manager.save_optimization_log(
        strategy_key, len(ic_data), "IC缩放",
        round(float(avg_ic), 4), None, None,
        {"changes": changes}
    )

    return {
        "method": "IC缩放",
        "strategy": strategy_key,
        "sample_count": len(ic_data),
        "avg_abs_ic": round(float(avg_ic), 4),
        "changes": changes,
    }


# ============================================================
#  优化方法 2: 网格搜索 (轻量级)
# ============================================================

def optimize_by_grid_search(strategy_key, top_n=5):
    """
    对 IC 最高的 top_n 个因子在 [-3, +3] 范围内做网格搜索
    步长 = 1，搜索组合数 = 7^top_n（top_n=5时为16807，可接受）
    """
    config = FACTOR_CONFIGS.get(strategy_key)
    if not config:
        return {"error": f"未知策略: {strategy_key}"}

    ic_data = compute_ic_analysis(strategy_key)
    if not ic_data or len(ic_data) < 10:
        return {"error": "数据不足"}

    # 取 IC 绝对值最高的 top_n 个因子
    sorted_ic = sorted(ic_data, key=lambda x: abs(x["ic_1d"]), reverse=True)[:top_n]

    # 生成网格搜索范围
    from itertools import product
    delta_range = [-3, -2, -1, 0, 1, 2, 3]

    # 找到对应的因子配置
    target_factors = []
    for ic_item in sorted_ic:
        db_col = ic_item["factor"]
        for f in config["rewards"]:
            if f["db_col"] == db_col:
                target_factors.append({
                    "name": f["name"],
                    "db_col": db_col,
                    "original": f["weight"],
                    "ic": ic_item["ic_1d"],
                })
                break
        if len(target_factors) >= top_n:
            break

    if len(target_factors) < 2:
        # 因子太少，退化为 IC 缩放
        return optimize_by_ic(strategy_key, learning_rate=0.15)

    # 简化网格：对每个因子尝试 +/- {0,1,2}
    best_config = None
    best_score = -999

    # 生成网格
    grid = list(product(delta_range[:5], repeat=len(target_factors)))  # [-2,-1,0,1,2] → 5^n
    if len(grid) > 5000:
        grid = grid[:5000]  # 限制搜索量

    # 获取历史 scores + returns 用于评估
    ic_map = {item["factor"]: item["ic_1d"] for item in ic_data}
    avg_pos_ic = np.mean([v for v in ic_map.values() if v > 0]) if any(v > 0 for v in ic_map.values()) else 0.01
    avg_neg_ic = np.mean([v for v in ic_map.values() if v < 0]) if any(v < 0 for v in ic_map.values()) else -0.01

    for deltas in grid:
        combined_score = 0
        for i, (tf, delta) in enumerate(zip(target_factors, deltas)):
            new_w = tf["original"] + delta
            new_w = max(1, min(30, new_w))
            ic_val = tf["ic"]
            # 分数 = IC * 新权重 - 变化成本
            combined_score += ic_val * new_w - abs(delta) * 0.1

        if combined_score > best_score:
            best_score = combined_score
            best_config = deltas

    # 构建优化结果
    changes = []
    weights_list = []

    for i, (tf, delta) in enumerate(zip(target_factors, best_config or [0]*len(target_factors))):
        new_w = max(1, min(30, tf["original"] + delta))
        changes.append({
            "factor": tf["name"],
            "original": tf["original"],
            "new": new_w,
            "ic": round(tf["ic"], 4),
            "delta": delta,
        })
        weights_list.append({
            "factor_name": tf["name"],
            "factor_type": "reward",
            "original_weight": tf["original"],
            "current_weight": tf["original"],
            "optimized_weight": new_w,
            "ic_value": round(tf["ic"], 4),
            "confidence": min(1.0, abs(tf["ic"]) * 10),
            "sample_count": len(ic_data),
        })

    # 未参与网格的因子保持原权重
    changed_names = {c["factor"] for c in changes}
    for f in config["rewards"]:
        if f["name"] not in changed_names:
            weights_list.append({
                "factor_name": f["name"],
                "factor_type": "reward",
                "original_weight": f["weight"],
                "current_weight": f["weight"],
                "optimized_weight": f["weight"],
                "ic_value": round(ic_map.get(f["db_col"], 0), 4),
                "confidence": 0.5,
                "sample_count": len(ic_data),
            })

    db_manager.save_factor_weights(strategy_key, weights_list)
    avg_ic = np.mean([abs(c["ic"]) for c in changes]) if changes else 0
    db_manager.save_optimization_log(
        strategy_key, len(ic_data), "网格搜索",
        round(float(avg_ic), 4), None, None,
        {"changes": changes, "grid_size": len(grid)}
    )

    return {
        "method": "网格搜索",
        "strategy": strategy_key,
        "sample_count": len(ic_data),
        "grid_size": len(grid),
        "changes": changes,
    }


# ============================================================
#  主优化入口
# ============================================================

def optimize_strategy(strategy_key, method="auto"):
    """
    优化单个策略
    method: "ic" | "grid" | "auto"
    auto: 样本 >= 30 用网格搜索，否则用 IC 缩放
    """
    if strategy_key not in FACTOR_CONFIGS:
        return {"error": f"未知策略: {strategy_key}"}

    ic_data = compute_ic_analysis(strategy_key)
    sample_count = len(ic_data) if ic_data else 0

    if sample_count < 5:
        return {
            "strategy": strategy_key,
            "status": "数据不足",
            "message": f"仅有 {sample_count} 条有效数据，需要至少 5 条",
            "sample_count": sample_count,
        }

    if method == "auto":
        method = "grid" if sample_count >= 30 else "ic"

    if method == "grid":
        result = optimize_by_grid_search(strategy_key)
    else:
        result = optimize_by_ic(strategy_key)

    result["sample_count"] = sample_count
    return result


def optimize_all():
    """优化全部策略"""
    results = {}
    for key in FACTOR_CONFIGS:
        try:
            results[key] = optimize_strategy(key)
        except Exception as e:
            results[key] = {"error": str(e)}
    return results


def get_optimized_weights(strategy_key):
    """
    获取优化后的权重（用于策略读取）
    返回: {factor_name: optimized_weight}
    """
    weights = db_manager.get_factor_weights(strategy_key)
    if not weights:
        # 返回默认权重
        config = FACTOR_CONFIGS.get(strategy_key, {})
        return {f["name"]: f["weight"] for f in config.get("rewards", [])}

    result = {}
    for w in weights:
        # 使用 optimized_weight > current_weight > original_weight
        weight = w.get("optimized_weight") or w.get("current_weight") or w.get("original_weight", 0)
        result[w["factor_name"]] = weight

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  策略优化器 — 因子分析 & 权重自动调整")
    print("=" * 60)

    for key in ["momentum", "oversold", "volume_price", "breakout"]:
        print(f"\n--- {key} ---")
        result = optimize_strategy(key, method="auto")
        if "error" in result:
            print(f"  {result['error']}")
        elif "message" in result:
            print(f"  {result['message']}")
        else:
            print(f"  方法: {result['method']}  样本: {result['sample_count']}")
            for c in result.get("changes", [])[:8]:
                arrow = "↑" if c["new"] > c["original"] else ("↓" if c["new"] < c["original"] else "→")
                print(f"    {c['factor']}: {c['original']} {arrow} {c['new']}  (IC={c['ic']})")
