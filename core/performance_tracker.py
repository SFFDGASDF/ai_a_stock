"""
绩效追踪器 — 追踪历史选股的后续实际表现，计算 T+N 收益率和统计指标
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
import core.db_manager as db_manager
from core.stock_utils import get_client


def track_pick_performance(pick_id, code, run_date_str):
    """
    追踪单只股票选股后的实际表现
    返回: perf_data dict 或 None
    """
    try:
        client = get_client()
        run_date = datetime.strptime(run_date_str, "%Y-%m-%d")

        # 获取选股日之后的 K 线数据（至少需要 15 个交易日）
        bars = client.bars(symbol=code, category=4, offset=30)
        if bars is None:
            return None

        # mootdx 可能返回 datetime 同时是 index 和列名，先修复歧义
        df = pd.DataFrame(bars) if not isinstance(bars, pd.DataFrame) else bars.copy()
        try:
            dup_cols = set(df.index.names) & set(df.columns)
            for col in dup_cols:
                if col and col != '':
                    df = df.drop(columns=[col])
        except:
            pass
        if df.index.name == 'datetime' or 'datetime' in (df.index.names or []):
            df = df.reset_index()
        if 'datetime' not in df.columns:
            for col in df.columns:
                if 'datetime' in str(col).lower() or 'date' in str(col).lower():
                    df = df.rename(columns={col: 'datetime'})
                    break

        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime')

        if len(df) < 5:
            return None

        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)

        # 找到选股日当天或之后最近的交易日在数据中的位置
        # 通过 datetime 匹配
        run_dt = pd.Timestamp(run_date_str)
        mask = df['datetime'] >= run_dt
        if not mask.any():
            return None

        idx_start = mask.idxmax()
        start_pos = df.index.get_loc(idx_start)

        # 选股日收盘价
        pick_price = float(close.iloc[start_pos])

        if pick_price <= 0:
            return None

        remaining = len(close) - start_pos - 1

        ret_1d = None
        ret_3d = None
        ret_5d = None
        ret_10d = None
        max_ret_3d = None
        max_ret_5d = None
        min_ret_3d = None
        min_ret_5d = None

        if remaining >= 1:
            ret_1d = round((float(close.iloc[start_pos + 1]) / pick_price - 1) * 100, 2)

        if remaining >= 3:
            p3 = float(close.iloc[start_pos + 3])
            ret_3d = round((p3 / pick_price - 1) * 100, 2)
            # 区间最大/最小
            segment_high = [float(high.iloc[start_pos + i]) for i in range(1, 4)]
            segment_low = [float(low.iloc[start_pos + i]) for i in range(1, 4)]
            max_ret_3d = round((max(segment_high) / pick_price - 1) * 100, 2)
            min_ret_3d = round((min(segment_low) / pick_price - 1) * 100, 2)

        if remaining >= 5:
            p5 = float(close.iloc[start_pos + 5])
            ret_5d = round((p5 / pick_price - 1) * 100, 2)
            segment_high = [float(high.iloc[start_pos + i]) for i in range(1, 6)]
            segment_low = [float(low.iloc[start_pos + i]) for i in range(1, 6)]
            max_ret_5d = round((max(segment_high) / pick_price - 1) * 100, 2)
            min_ret_5d = round((min(segment_low) / pick_price - 1) * 100, 2)

        if remaining >= 10:
            ret_10d = round((float(close.iloc[start_pos + 10]) / pick_price - 1) * 100, 2)

        check_date = df['datetime'].iloc[start_pos + min(remaining, 5)].strftime("%Y-%m-%d")

        return {
            "check_date": check_date,
            "ret_1d": ret_1d, "ret_3d": ret_3d,
            "ret_5d": ret_5d, "ret_10d": ret_10d,
            "max_ret_3d": max_ret_3d, "max_ret_5d": max_ret_5d,
            "min_ret_3d": min_ret_3d, "min_ret_5d": min_ret_5d,
        }
    except Exception as e:
        return None


def run_performance_check():
    """检查所有未追踪的 picks 并更新绩效数据"""
    picks = db_manager.get_unchecked_picks(days_ago=0)

    if not picks:
        print(f"[PerfTracker] 没有需要追踪的 picks")
        return {"checked": 0, "updated": 0}

    print(f"[PerfTracker] 开始追踪 {len(picks)} 个 picks...")
    updated = 0
    errors = 0

    for i, pick in enumerate(picks):
        try:
            # 跳过太新的数据（不足 1 个交易日）
            run_date = datetime.strptime(pick["run_date"], "%Y-%m-%d")
            days_ago = (datetime.now() - run_date).days
            if days_ago < 1:
                continue

            perf = track_pick_performance(
                pick["id"], pick["code"], pick["run_date"]
            )
            if perf:
                db_manager.save_performance(pick["id"], pick["run_date"], perf)
                updated += 1
        except Exception as e:
            errors += 1

        if (i + 1) % 20 == 0:
            print(f"[PerfTracker] 进度: {i + 1}/{len(picks)}, 已更新 {updated}")
            time.sleep(0.1)

    print(f"[PerfTracker] 完成: 检查 {len(picks)}, 更新 {updated}, 错误 {errors}")
    return {"checked": len(picks), "updated": updated, "errors": errors}


def compute_sharpe_ratio(returns):
    """计算年化夏普比率（假设日收益率）"""
    if not returns or len(returns) < 2:
        return 0
    arr = np.array(returns)
    avg = np.mean(arr)
    std = np.std(arr, ddof=1)
    if std == 0:
        return 0
    return round(avg / std * np.sqrt(250), 2)


def compute_max_drawdown(returns):
    """计算最大回撤"""
    if not returns:
        return 0
    cum = np.cumprod(np.array(returns) / 100 + 1)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak * 100
    return round(abs(min(dd)), 2)


def get_full_stats(strategy_key=None):
    """
    获取完整的策略统计报告
    包含: 胜率、平均收益、盈亏比、夏普比率、最大回撤、IC排名
    """
    stats = db_manager.get_strategy_stats(strategy_key or "all")
    result = {}

    for key, s in stats.items():
        total = s.get("total_picks", 0)
        winrate = s.get("winrate_1d", 0)
        avg_ret = s.get("avg_ret_1d", 0) or 0
        avg_ret_3d = s.get("avg_ret_3d", 0) or 0
        avg_ret_5d = s.get("avg_ret_5d", 0) or 0

        result[key] = {
            "total_picks": total,
            "winrate_1d": winrate,
            "winrate_3d": s.get("winrate_3d", 0),
            "winrate_5d": s.get("winrate_5d", 0),
            "avg_ret_1d": round(avg_ret, 2),
            "avg_ret_3d": round(avg_ret_3d, 2),
            "avg_ret_5d": round(avg_ret_5d, 2),
            "profit_loss_ratio": s.get("profit_loss_ratio", 0),
            "max_ret_5d": round(s.get("max_ret_5d", 0) or 0, 2),
            "min_ret_5d": round(s.get("min_ret_5d", 0) or 0, 2),
        }

        # IC 分析
        if key != "all":
            ic = db_manager.get_ic_analysis(key)
            result[key]["ic_analysis"] = ic[:8] if ic else []

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("  绩效追踪器 — 检查历史选股表现")
    print("=" * 60)
    run_performance_check()
    print("\n  策略统计:")
    full = get_full_stats()
    for k, v in full.items():
        print(f"\n  [{k}] 样本{v['total_picks']}  T+1胜率{v['winrate_1d']}%"
              f"  平均{v['avg_ret_1d']}%  盈亏比{v['profit_loss_ratio']}")
