"""
统一配置管理 — 所有可调参数集中在此文件
支持环境变量覆盖（.env 文件）
"""
import os
from pathlib import Path

# ============================================================
#  项目路径
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = BASE_DIR / "charts"
STRATEGIES_DIR = BASE_DIR / "strategies"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
DB_PATH = BASE_DIR / "strategy_data.db"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)


# ============================================================
#  Web 服务器
# ============================================================
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"


# ============================================================
#  数据源
# ============================================================
# 通达信行情服务器
TDX_MARKET = "std"                      # 标准市场
TDX_REQUEST_TIMEOUT = 15                # 请求超时（秒）

# 东方财富 API
EASTMONEY_BASE = "https://push2his.eastmoney.com/api/qt/clist/get"
EASTMONEY_FIELDS_TURNOVER = "f8,f12,f62,f184"
EASTMONEY_FIELDS_FUNDAMENTAL = "f9,f12,f20,f23,f115"
EASTMONEY_FIELDS_SENTIMENT = "f2,f3,f12"

# 腾讯行情 API
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="

# 同花顺 API
THS_HOT_URL = "http://zx.10jqka.com.cn/event/api/getharden"


# ============================================================
#  行情扫描参数
# ============================================================
QUOTE_BATCH_SIZE = 80                   # 每批拉取股票数
QUOTE_BATCH_DELAY = 0.05               # 批次间隔（秒）

# 各策略筛选阈值
MOMENTUM_CHG_RANGE = (3, 7)             # 动量策略：涨幅范围
MOMENTUM_CHG_FALLBACK = (2, 8)          # 动量策略：放宽后涨幅范围
MOMENTUM_MAX_CANDIDATES = 200           # 最大候选数
MOMENTUM_MIN_AMOUNT = 30_000_000        # 最小成交额

OVERSOLD_CHG_RANGE = (-8, -2)           # 超跌策略：跌幅范围
OVERSOLD_MAX_CANDIDATES = 80            # 最大候选数
OVERSOLD_MIN_AMOUNT = 30_000_000        # 最小成交额
OVERSOLD_MIN_PRICE = 3.0                # 最低股价

VOLUME_PRICE_CHG_RANGE = (1, 8)         # 量价共振：涨幅范围
VOLUME_PRICE_MAX_CANDIDATES = 300       # 最大候选数
VOLUME_PRICE_MIN_AMOUNT = 10_000_000    # 最小成交额
VOLUME_PRICE_MIN_PRICE = 2.0            # 最低股价
VOLUME_PRICE_TURNOVER_RANGE = (2, 20)   # 换手率范围

BREAKOUT_CHG_RANGE = (0.5, 6)           # 突破策略：涨幅范围
BREAKOUT_MAX_CANDIDATES = 200           # 最大候选数
BREAKOUT_MIN_AMOUNT = 20_000_000        # 最小成交额
BREAKOUT_MIN_PRICE = 3.0                # 最低股价
BREAKOUT_MIN_VR = 1.2                   # 突破最小量比


# ============================================================
#  大盘环境检测
# ============================================================
MARKET_SAMPLE_SIZE = 500                # 涨跌比采样数
MARKET_UP_THRESHOLD = 0.5               # 上涨阈值


# ============================================================
#  技术分析
# ============================================================
KLINE_OFFSET = 120                      # K线获取数量（日）
MIN_KLINE_BARS = 60                     # 最少K线数

# ATR 止损
ATR_MULTIPLIER = 1.5                    # ATR 倍数
ATR_STOP_MIN_PCT = 2.0                  # 最小止损百分比
ATR_STOP_MAX_PCT = 5.0                  # 最大止损百分比


# ============================================================
#  基本面过滤
# ============================================================
PE_MIN = 0                              # PE 最小值（<0 为亏损）
PE_MAX = 200                            # PE 最大值
PB_MAX = 10                             # PB 最大值
MV_MIN = 2_000_000_000                  # 最小市值（20亿）
MV_MIN_OVERSOLD = 3_000_000_000         # 超跌策略最小市值（30亿）


# ============================================================
#  RPS 排名
# ============================================================
RPS_WINDOW = 20                         # RPS 计算窗口（日）
RPS_SAMPLE_SIZE = 500                   # RPS 基准采样数


# ============================================================
#  市场情绪 Gate（策略启动前检测）
# ============================================================
SENTIMENT_BROKEN_RATE_MAX = 35          # 最大炸板率（%）
SENTIMENT_TEMP_MIN = 25                 # 最低市场温度
SENTIMENT_LIMIT_UP_MIN = 20             # 最低涨停家数
SENTIMENT_LIMIT_DOWN_MAX = 50           # 最大跌停家数


# ============================================================
#  策略结果输出
# ============================================================
TOP_N_DISPLAY = 15                      # 策略输出显示前 N 名
TOP_N_SAVE = 60                         # 综合选股合并保存前 N 名


# ============================================================
#  安全门阈值
# ============================================================
SAFE_GATE = {
    "momentum": {
        "vr_min": 0.6, "rsi_max": 72, "dev_max": 18,
        "chg_5d_max": 10, "turnover_min": 1, "turnover_max": 20,
        "up_days_max": 3, "j_max": 105, "upper_shadow_max": 4,
        "rps_min": 35,
    },
    "oversold": {
        "vr_min": 0.5, "rsi_max": 65, "dev_max": 25,
        "chg_5d_min": -12, "down_days_max": 4, "turnover_min": 0.6,
        "rps_min": 25,
    },
    "volume_price": {
        "vr_min": 1.0, "dev_max": 18, "up_days_max": 3,
        "main_net_min": -3_000_000, "boll_max": 92, "upper_shadow_max": 4,
        "rps_min": 35,
    },
    "breakout": {
        "vr_min": 1.2, "dev_max": 18, "up_days_max": 3,
        "main_net_min": -3_000_000, "upper_shadow_max": 4,
        "rps_min": 35,
    },
}


# ============================================================
#  推荐评分阈值（根据大盘环境调整）
# ============================================================
SCORE_THRESHOLD = {
    "momentum":     {"bull": 75, "bear": 80},
    "oversold":     {"bull": 72, "bear": 80},
    "volume_price": {"bull": 70, "bear": 78},
    "breakout":     {"bull": 70, "bear": 78},
}


# ============================================================
#  后台调度
# ============================================================
SCHEDULER_CHECK_INTERVAL = 3600         # 绩效检查间隔（秒）
SCHEDULER_OPTIMIZE_THRESHOLD = 30       # 触发优化的新数据阈值
SCHEDULER_AUTO_OPTIMIZE = True          # 是否自动优化


# ============================================================
#  策略进化
# ============================================================
OPTIMIZE_MIN_SAMPLES = 5                # 最少样本数
OPTIMIZE_GRID_SAMPLES = 30              # 网格搜索最低样本数
OPTIMIZE_LEARNING_RATE = 0.1            # IC 缩放学习率
OPTIMIZE_GRID_TOP_N = 5                 # 网格搜索 TOP N 因子
OPTIMIZE_WEIGHT_MIN = 1                 # 权重最小值
OPTIMIZE_WEIGHT_MAX = 30                # 权重最大值
OPTIMIZE_WEIGHT_DELTA = 3               # 网格搜索步长


# ============================================================
#  日志
# ============================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
