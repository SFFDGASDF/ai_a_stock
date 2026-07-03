"""
数据库管理模块 — SQLite 持久化策略选股记录、绩效追踪、因子权重
"""
import sqlite3
import json
import os
import time
from datetime import datetime
from core.config import DB_PATH


def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    c = conn.cursor()

    # 策略运行记录
    c.execute("""
        CREATE TABLE IF NOT EXISTS strategy_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            strategy_key TEXT NOT NULL,
            run_date TEXT NOT NULL,
            run_datetime TEXT NOT NULL,
            market_env TEXT,
            market_score INTEGER,
            up_ratio REAL,
            down_ratio REAL,
            sentiment_score REAL,
            sentiment_label TEXT,
            broken_rate REAL,
            limit_up_count INTEGER,
            limit_down_count INTEGER,
            total_candidates INTEGER,
            top15_avg_score REAL,
            recommendation_code TEXT,
            recommendation_name TEXT,
            recommendation_score INTEGER,
            recommendation_price REAL,
            recommendation_chg REAL
        )
    """)

    # 每只被选中的股票及全部因子得分
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            strategy_key TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            rank INTEGER,
            price REAL,
            chg_today REAL,
            score INTEGER,
            rsi6 REAL,
            rsi14 REAL,
            vr REAL,
            turnover REAL,
            main_net REAL,
            rps20 REAL,
            rps60 REAL,
            dev REAL,
            chg_3d REAL,
            chg_5d REAL,
            chg_10d REAL,
            chg_20d REAL,
            up_days INTEGER,
            down_days INTEGER,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            ma60 REAL,
            ma5_slope REAL,
            ma20_slope REAL,
            boll_pos REAL,
            boll_width REAL,
            dif REAL,
            dea REAL,
            macdh REAL,
            k REAL,
            d_val REAL,
            j REAL,
            atr14 REAL,
            limit_up_count INTEGER,
            upper_shadow REAL,
            lower_shadow REAL,
            amount REAL,
            pe REAL,
            pb REAL,
            total_mv REAL,
            stop_pct REAL,
            stop_price REAL,
            details_json TEXT,
            risk_tags TEXT,
            is_recommendation INTEGER DEFAULT 0,
            run_date TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES strategy_runs(id)
        )
    """)

    # 选股后实际表现
    c.execute("""
        CREATE TABLE IF NOT EXISTS pick_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pick_id INTEGER NOT NULL UNIQUE,
            run_date TEXT NOT NULL,
            check_date TEXT NOT NULL,
            ret_1d REAL,
            ret_3d REAL,
            ret_5d REAL,
            ret_10d REAL,
            max_ret_3d REAL,
            max_ret_5d REAL,
            min_ret_3d REAL,
            min_ret_5d REAL,
            is_profitable_1d INTEGER,
            is_profitable_3d INTEGER,
            is_profitable_5d INTEGER,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (pick_id) REFERENCES stock_picks(id)
        )
    """)

    # 因子权重与优化历史
    c.execute("""
        CREATE TABLE IF NOT EXISTS factor_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_key TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            factor_type TEXT NOT NULL DEFAULT 'reward',
            current_weight REAL NOT NULL,
            optimized_weight REAL,
            original_weight REAL,
            ic_value REAL,
            ic_ir REAL,
            confidence REAL DEFAULT 0.5,
            sample_count INTEGER DEFAULT 0,
            update_date TEXT NOT NULL,
            UNIQUE(strategy_key, factor_name)
        )
    """)

    # 优化历史日志
    c.execute("""
        CREATE TABLE IF NOT EXISTS optimization_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_key TEXT NOT NULL,
            optimize_date TEXT NOT NULL,
            sample_count INTEGER,
            method TEXT,
            avg_ic REAL,
            winrate_before REAL,
            winrate_after REAL,
            detail_json TEXT
        )
    """)

    # ==================== AI 多智能体分析记录 ====================
    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_runs (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT,
            trade_date TEXT NOT NULL,
            rating TEXT,
            summary TEXT,
            elapsed_seconds REAL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            result_json TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER,
            report_text TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (run_id) REFERENCES ai_analysis_runs(id)
        )
    """)

    # 索引
    c.execute("CREATE INDEX IF NOT EXISTS idx_picks_run ON stock_picks(run_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_picks_code ON stock_picks(code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_picks_date ON stock_picks(run_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_perf_pick ON pick_performance(pick_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_date ON strategy_runs(run_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_runs_strategy ON strategy_runs(strategy_key)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_runs_date ON ai_analysis_runs(trade_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ai_stages_run ON ai_analysis_stages(run_id)")

    conn.commit()
    conn.close()


# ============================================================
#  策略运行记录
# ============================================================

def save_strategy_run(strategy_key, strategy_name, result, sentiment=None, env_data=None):
    """保存一次策略运行记录"""
    conn = get_conn()
    c = conn.cursor()

    now = datetime.now()
    run_date = now.strftime("%Y-%m-%d")
    run_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

    stocks = result.get("stocks", [])
    rec = result.get("recommendation")

    top15_scores = [s.get("score", 0) for s in stocks[:15]]
    avg_score = sum(top15_scores) / len(top15_scores) if top15_scores else 0

    c.execute("""
        INSERT INTO strategy_runs (
            strategy_name, strategy_key, run_date, run_datetime,
            market_env, market_score, up_ratio, down_ratio,
            sentiment_score, sentiment_label, broken_rate,
            limit_up_count, limit_down_count,
            total_candidates, top15_avg_score,
            recommendation_code, recommendation_name,
            recommendation_score, recommendation_price, recommendation_chg
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        strategy_name, strategy_key, run_date, run_datetime,
        env_data.get("label", "") if env_data else "",
        env_data.get("score", 0) if env_data else 0,
        env_data.get("up_ratio", 0) if env_data else 0,
        env_data.get("down_ratio", 0) if env_data else 0,
        sentiment.get("sentiment_score", 50) if sentiment else 50,
        sentiment.get("sentiment_label", "") if sentiment else "",
        sentiment.get("broken_rate", 0) if sentiment else 0,
        sentiment.get("limit_up_count", 0) if sentiment else 0,
        sentiment.get("limit_down_count", 0) if sentiment else 0,
        len(stocks), round(avg_score, 1),
        rec.get("code") if rec else None,
        rec.get("name") if rec else None,
        rec.get("score") if rec else None,
        rec.get("price") if rec else None,
        rec.get("chg") if rec else None,
    ))

    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id


def save_stock_picks(run_id, strategy_key, stocks, run_date=None):
    """保存一批选股结果"""
    if not stocks:
        return

    conn = get_conn()
    c = conn.cursor()

    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    for i, s in enumerate(stocks):
        details = s.get("details", [])
        if isinstance(details, list):
            details_str = json.dumps([{"name": str(d[0]), "score": d[1]} for d in details], ensure_ascii=False)
        else:
            details_str = str(details)

        risk_tags = s.get("risk_tags", "")
        if isinstance(risk_tags, list):
            risk_tags = ",".join(risk_tags)

        is_rec = 1 if s.get("is_recommendation") else 0

        c.execute("""
            INSERT INTO stock_picks (
                run_id, strategy_key, code, name, rank, price, chg_today, score,
                rsi6, rsi14, vr, turnover, main_net, rps20, rps60,
                dev, chg_3d, chg_5d, chg_10d, chg_20d,
                up_days, down_days, ma5, ma10, ma20, ma60,
                ma5_slope, ma20_slope, boll_pos, boll_width,
                dif, dea, macdh, k, d_val, j, atr14,
                limit_up_count, upper_shadow, lower_shadow, amount,
                pe, pb, total_mv, stop_pct, stop_price,
                details_json, risk_tags, is_recommendation, run_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, strategy_key, s.get("code"), s.get("name"),
            i + 1, s.get("price"), s.get("chg", s.get("chg_today", 0)),
            s.get("score"),
            s.get("rsi6"), s.get("rsi14"), s.get("vr", s.get("volume_ratio")),
            s.get("turnover"), s.get("main_net"), s.get("rps20"), s.get("rps60"),
            s.get("dev", s.get("deviation")),
            s.get("chg_3d"), s.get("chg_5d"), s.get("chg_10d"), s.get("chg_20d"),
            s.get("up_days"), s.get("down_days"),
            s.get("ma5"), s.get("ma10"), s.get("ma20"), s.get("ma60"),
            s.get("ma5_slope"), s.get("ma20_slope"),
            s.get("boll_pos"), s.get("boll_width"),
            s.get("dif"), s.get("dea"), s.get("macdh"),
            s.get("k"), s.get("d_val"), s.get("j"),
            s.get("atr14"), s.get("limit_up_count"),
            s.get("upper_shadow"), s.get("lower_shadow"),
            s.get("amount"),
            s.get("pe"), s.get("pb"), s.get("total_mv"),
            s.get("stop_pct"), s.get("stop_price"),
            details_str, risk_tags, is_rec, run_date,
        ))

    conn.commit()
    conn.close()


# ============================================================
#  绩效数据操作
# ============================================================

def get_unchecked_picks(days_ago=1):
    """获取尚未检查绩效的 picks（N天前的）"""
    conn = get_conn()
    c = conn.cursor()

    target_date = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                   .strftime("%Y-%m-%d"))

    c.execute("""
        SELECT sp.id, sp.code, sp.price, sp.run_date, sp.strategy_key
        FROM stock_picks sp
        LEFT JOIN pick_performance pp ON sp.id = pp.pick_id
        WHERE pp.id IS NULL
          AND sp.run_date <= ?
        ORDER BY sp.run_date DESC
        LIMIT 500
    """, (target_date,))

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_performance(pick_id, run_date, perf_data):
    """保存单只股票的绩效数据"""
    conn = get_conn()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        INSERT OR REPLACE INTO pick_performance (
            pick_id, run_date, check_date,
            ret_1d, ret_3d, ret_5d, ret_10d,
            max_ret_3d, max_ret_5d, min_ret_3d, min_ret_5d,
            is_profitable_1d, is_profitable_3d, is_profitable_5d,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pick_id, run_date, perf_data.get("check_date", run_date),
        perf_data.get("ret_1d"), perf_data.get("ret_3d"), perf_data.get("ret_5d"),
        perf_data.get("ret_10d"),
        perf_data.get("max_ret_3d"), perf_data.get("max_ret_5d"),
        perf_data.get("min_ret_3d"), perf_data.get("min_ret_5d"),
        1 if (perf_data.get("ret_1d") or 0) > 0 else 0,
        1 if (perf_data.get("ret_3d") or 0) > 0 else 0,
        1 if (perf_data.get("ret_5d") or 0) > 0 else 0,
        now,
    ))

    conn.commit()
    conn.close()


def get_strategy_stats(strategy_key=None, days=90):
    """获取策略统计信息"""
    conn = get_conn()
    c = conn.cursor()

    cutoff = (datetime.now().strftime("%Y-%m-%d"))

    if strategy_key == "all" or strategy_key is None:
        strategy_cond = ""
        params = []
    else:
        strategy_cond = "AND sp.strategy_key = ?"
        params = [strategy_key]

    c.execute(f"""
        SELECT
            sp.strategy_key,
            COUNT(DISTINCT sp.id) as total_picks,
            COUNT(DISTINCT CASE WHEN pp.is_profitable_1d = 1 THEN sp.id END) as wins_1d,
            COUNT(DISTINCT CASE WHEN pp.is_profitable_3d = 1 THEN sp.id END) as wins_3d,
            COUNT(DISTINCT CASE WHEN pp.is_profitable_5d = 1 THEN sp.id END) as wins_5d,
            AVG(pp.ret_1d) as avg_ret_1d,
            AVG(pp.ret_3d) as avg_ret_3d,
            AVG(pp.ret_5d) as avg_ret_5d,
            AVG(CASE WHEN pp.ret_1d > 0 THEN pp.ret_1d END) as avg_gain_1d,
            AVG(CASE WHEN pp.ret_1d < 0 THEN pp.ret_1d END) as avg_loss_1d,
            MAX(pp.ret_5d) as max_ret_5d,
            MIN(pp.ret_5d) as min_ret_5d
        FROM stock_picks sp
        JOIN pick_performance pp ON sp.id = pp.pick_id
        WHERE sp.run_date <= ? {strategy_cond}
        GROUP BY sp.strategy_key
    """, [cutoff] + params)

    rows = c.fetchall()
    stats = {}
    for r in rows:
        d = dict(r)
        key = d.pop("strategy_key")
        total = d["total_picks"]
        d["winrate_1d"] = round(d["wins_1d"] / total * 100, 1) if total > 0 else 0
        d["winrate_3d"] = round(d["wins_3d"] / total * 100, 1) if total > 0 else 0
        d["winrate_5d"] = round(d["wins_5d"] / total * 100, 1) if total > 0 else 0
        avg_gain = d.get("avg_gain_1d") or 1
        avg_loss = abs(d.get("avg_loss_1d") or 1)
        d["profit_loss_ratio"] = round(avg_gain / avg_loss, 2) if avg_loss > 0 else 0
        stats[key] = d

    conn.close()
    return stats


def get_recent_performance(strategy_key=None, limit=50):
    """获取最近N条选股的表现详情"""
    conn = get_conn()
    c = conn.cursor()

    if strategy_key and strategy_key != "all":
        cond = "AND sp.strategy_key = ?"
        params = [strategy_key, limit]
    else:
        cond = ""
        params = [limit]

    c.execute(f"""
        SELECT sp.code, sp.name, sp.price as pick_price, sp.score,
               sp.run_date, sp.strategy_key,
               pp.ret_1d, pp.ret_3d, pp.ret_5d,
               pp.is_profitable_1d, pp.is_profitable_3d, pp.is_profitable_5d
        FROM stock_picks sp
        JOIN pick_performance pp ON sp.id = pp.pick_id
        WHERE 1=1 {cond}
        ORDER BY sp.run_date DESC
        LIMIT ?
    """, params)

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  因子权重操作
# ============================================================

def get_factor_weights(strategy_key):
    """获取某策略的当前因子权重配置"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT factor_name, factor_type, current_weight, optimized_weight,
               original_weight, ic_value, ic_ir, confidence, sample_count
        FROM factor_weights
        WHERE strategy_key = ?
        ORDER BY ABS(current_weight) DESC
    """, (strategy_key,))

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_factor_weights(strategy_key, weights_list):
    """批量保存因子权重"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for w in weights_list:
        c.execute("""
            INSERT OR REPLACE INTO factor_weights (
                strategy_key, factor_name, factor_type,
                current_weight, optimized_weight, original_weight,
                ic_value, ic_ir, confidence, sample_count, update_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_key, w["factor_name"], w.get("factor_type", "reward"),
            w.get("current_weight", w.get("original_weight", 0)),
            w.get("optimized_weight"),
            w.get("original_weight", w.get("current_weight", 0)),
            w.get("ic_value"), w.get("ic_ir"),
            w.get("confidence", 0.5), w.get("sample_count", 0), now,
        ))

    conn.commit()
    conn.close()


def save_optimization_log(strategy_key, sample_count, method, avg_ic,
                          winrate_before, winrate_after, detail=None):
    """记录优化历史"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("""
        INSERT INTO optimization_log (
            strategy_key, optimize_date, sample_count, method,
            avg_ic, winrate_before, winrate_after, detail_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        strategy_key, now, sample_count, method,
        avg_ic, winrate_before, winrate_after,
        json.dumps(detail, ensure_ascii=False) if detail else None,
    ))

    conn.commit()
    conn.close()


def get_optimization_history(strategy_key=None, limit=20):
    """获取优化历史"""
    conn = get_conn()
    c = conn.cursor()

    if strategy_key and strategy_key != "all":
        c.execute("""
            SELECT * FROM optimization_log
            WHERE strategy_key = ?
            ORDER BY optimize_date DESC LIMIT ?
        """, (strategy_key, limit))
    else:
        c.execute("""
            SELECT * FROM optimization_log
            ORDER BY optimize_date DESC LIMIT ?
        """, (limit,))

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
#  统计查询
# ============================================================

def get_run_summary(strategy_key=None, days=30):
    """获取策略运行摘要"""
    conn = get_conn()
    c = conn.cursor()

    cutoff = (datetime.now().strftime("%Y-%m-%d"))

    if strategy_key and strategy_key != "all":
        cond = "AND sr.strategy_key = ?"
        params = [cutoff, strategy_key]
    else:
        cond = ""
        params = [cutoff]

    c.execute(f"""
        SELECT sr.strategy_key, sr.strategy_name,
               COUNT(*) as runs,
               AVG(sr.top15_avg_score) as avg_top15,
               AVG(sr.total_candidates) as avg_candidates,
               AVG(sr.recommendation_score) as avg_rec_score
        FROM strategy_runs sr
        WHERE sr.run_date <= ? {cond}
        GROUP BY sr.strategy_key
    """, params)

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ic_analysis(strategy_key, factor_names=None):
    """获取因子的IC分析数据"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT sp.*, pp.ret_1d, pp.ret_3d, pp.ret_5d
        FROM stock_picks sp
        JOIN pick_performance pp ON sp.id = pp.pick_id
        WHERE sp.strategy_key = ?
    """, (strategy_key,))

    rows = c.fetchall()
    conn.close()

    if not rows:
        return []

    import numpy as np
    try:
        from scipy import stats as scipy_stats
    except ImportError:
        return []

    data = [dict(r) for r in rows]
    factor_cols = [
        "score", "rsi14", "vr", "turnover", "main_net", "rps20",
        "dev", "chg_5d", "up_days", "boll_pos", "j",
        "limit_up_count", "ma5_slope", "pe",
    ]

    results = []
    for col in factor_cols:
        values = [d[col] for d in data if d[col] is not None]
        rets_1d = [d["ret_1d"] for d in data if d[col] is not None]

        if len(values) < 10:
            continue

        try:
            ic, p_value = scipy_stats.spearmanr(values, rets_1d)
            ic_3d, _ = scipy_stats.spearmanr(values, [d["ret_3d"] for d in data if d[col] is not None])

            results.append({
                "factor": col,
                "ic_1d": round(ic, 4) if not np.isnan(ic) else 0,
                "ic_3d": round(ic_3d, 4) if not np.isnan(ic_3d) else 0,
                "p_value": round(p_value, 4) if not np.isnan(p_value) else 1,
                "significant": p_value < 0.05 if not np.isnan(p_value) else False,
                "sample": len(values),
            })
        except:
            pass

    results.sort(key=lambda x: abs(x["ic_1d"]), reverse=True)
    return results


# ============================================================
#  AI 多智能体分析
# ============================================================

def save_ai_run(run_id, symbol, name, trade_date, rating, summary,
                result_json, stages, elapsed_seconds):
    """保存一次 AI 分析记录"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO ai_analysis_runs (
            id, symbol, name, trade_date, rating, summary,
            elapsed_seconds, result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id, symbol, name, trade_date, rating, summary,
        elapsed_seconds,
        json.dumps(result_json, ensure_ascii=False, default=str),
    ))

    # 保存各阶段报告
    stage_order_map = {
        "market": 1, "sentiment": 2, "fundamentals": 3,
        "debate": 4, "trader": 5, "risk": 6, "pm": 7,
    }
    for stage_name, report_text in stages.items():
        c.execute("""
            INSERT INTO ai_analysis_stages (run_id, stage_name, stage_order, report_text)
            VALUES (?, ?, ?, ?)
        """, (
            run_id, stage_name,
            stage_order_map.get(stage_name, 99),
            report_text[:10000],
        ))

    conn.commit()
    conn.close()


def get_ai_runs(limit=20):
    """获取历史 AI 分析记录"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id, symbol, name, trade_date, rating, summary,
               elapsed_seconds, created_at
        FROM ai_analysis_runs
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ai_report(run_id):
    """获取单次 AI 分析完整报告（含各阶段）"""
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM ai_analysis_runs WHERE id = ?", (run_id,))
    run = c.fetchone()
    if not run:
        conn.close()
        return None

    c.execute("""
        SELECT stage_name, stage_order, report_text
        FROM ai_analysis_stages
        WHERE run_id = ?
        ORDER BY stage_order
    """, (run_id,))
    stages = c.fetchall()

    result = dict(run)
    if result.get("result_json"):
        try:
            result["result_json"] = json.loads(result["result_json"])
        except Exception:
            pass
    result["stages"] = [dict(s) for s in stages]

    conn.close()
    return result


def get_ai_latest_by_codes(codes: list) -> dict:
    """批量获取多只股票的最新 AI 分析结果。
    返回 {code: {rating, summary, thesis, price_target, time_horizon, trade_date, run_id, elapsed_seconds}} 字典。
    """
    if not codes:
        return {}
    conn = get_conn()
    c = conn.cursor()
    placeholders = ",".join(["?" for _ in codes])
    c.execute(f"""
        SELECT r.symbol, r.name, r.rating, r.summary, r.trade_date, r.id as run_id, r.elapsed_seconds, r.result_json
        FROM ai_analysis_runs r
        INNER JOIN (
            SELECT symbol, MAX(created_at) as max_created
            FROM ai_analysis_runs
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
        ) latest ON r.symbol = latest.symbol AND r.created_at = latest.max_created
    """, codes)
    rows = c.fetchall()
    conn.close()
    result = {}
    for row in rows:
        d = dict(row)
        code = d.pop("symbol", "")
        code = code.split(".")[0] if "." in code else code
        # 从 result_json 中提取 price_target / time_horizon / thesis
        rj = d.pop("result_json", None)
        if rj:
            try:
                rj_obj = json.loads(rj) if isinstance(rj, str) else rj
                d["price_target"] = rj_obj.get("price_target", "")
                d["time_horizon"] = rj_obj.get("time_horizon", "")
                d["thesis"] = rj_obj.get("thesis", "")
            except Exception:
                pass
        result[code] = d
    return result


# 初始化
init_db()
