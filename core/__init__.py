"""
Core 库 — 公共工具、数据库、绩效追踪、策略优化、调度引擎
"""
from core.config import (
    BASE_DIR, DB_PATH,
    FLASK_HOST, FLASK_PORT,
    QUOTE_BATCH_SIZE, KLINE_OFFSET, MIN_KLINE_BARS,
    ATR_MULTIPLIER, ATR_STOP_MIN_PCT, ATR_STOP_MAX_PCT,
    SAFE_GATE, SCORE_THRESHOLD,
    SCHEDULER_CHECK_INTERVAL, SCHEDULER_OPTIMIZE_THRESHOLD, SCHEDULER_AUTO_OPTIMIZE,
    OPTIMIZE_MIN_SAMPLES, OPTIMIZE_LEARNING_RATE,
)

__all__ = [
    "config",
    "logging_config",
    "stock_utils",
    "db_manager",
    "performance_tracker",
    "strategy_optimizer",
    "scheduler",
]
