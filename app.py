"""
主入口 — 启动 Web 仪表盘 + 后台调度
用法: python app.py
"""
import sys
import os

# 确保项目根目录在 sys.path 中
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from core.logging_config import logger

# 导入 Web 应用和调度器
from web.dashboard import app
from web.ai_analyst_api import ai_bp
import core.scheduler as bg_scheduler

# 注册 AI 分析蓝图
app.register_blueprint(ai_bp)


def main():
    """启动应用"""
    logger.info("=" * 60)
    logger.info("  AI A-Stock 量化分析系统 v4.3")
    logger.info("  Web 仪表盘: http://%s:%s", FLASK_HOST, FLASK_PORT)
    logger.info("  四策略 + 绩效追踪 + 自动优化")
    logger.info("=" * 60)

    # 启动后台调度（绩效追踪 + 自动优化）
    bg_scheduler.start_scheduler()

    # 启动 Flask
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        threaded=True,
    )


if __name__ == "__main__":
    main()
