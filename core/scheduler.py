"""
自动调度器 — 后台线程定期追踪绩效、触发优化
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import time
from datetime import datetime
from core.config import SCHEDULER_CHECK_INTERVAL, SCHEDULER_OPTIMIZE_THRESHOLD, SCHEDULER_AUTO_OPTIMIZE


# 调度配置
CHECK_INTERVAL_SECONDS = SCHEDULER_CHECK_INTERVAL
OPTIMIZE_THRESHOLD = SCHEDULER_OPTIMIZE_THRESHOLD
AUTO_OPTIMIZE = SCHEDULER_AUTO_OPTIMIZE


class Scheduler:
    """后台调度器 — 管理绩效追踪和自动优化任务"""

    def __init__(self):
        self._running = False
        self._thread = None
        self._last_check = None
        self._last_optimize = None
        self._status = {
            "running": False,
            "last_check": None,
            "last_optimize": None,
            "total_checks": 0,
            "total_optimizes": 0,
            "total_picks_tracked": 0,
        }

    def start(self):
        """启动后台调度线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="Scheduler")
        self._thread.start()
        self._status["running"] = True
        print("[Scheduler] 启动 — 绩效追踪间隔: {:.0f}分钟  自动优化: {}".format(
            CHECK_INTERVAL_SECONDS / 60,
            "开启" if AUTO_OPTIMIZE else "关闭"
        ))

    def stop(self):
        """停止调度"""
        self._running = False
        self._status["running"] = False
        print("[Scheduler] 已停止")

    def get_status(self):
        """获取调度器状态"""
        return self._status

    def trigger_check_now(self):
        """手动触发一次检查"""
        t = threading.Thread(target=self._do_check, daemon=True)
        t.start()
        return {"status": "triggered"}

    def trigger_optimize_now(self):
        """手动触发一次优化"""
        t = threading.Thread(target=self._do_optimize, daemon=True)
        t.start()
        return {"status": "triggered"}

    def _run_loop(self):
        """主调度循环"""
        # 启动后立即执行一次
        time.sleep(5)
        self._do_check()

        while self._running:
            try:
                time.sleep(CHECK_INTERVAL_SECONDS)
                if not self._running:
                    break
                self._do_check()

                # 自动优化
                if AUTO_OPTIMIZE and self._should_optimize():
                    self._do_optimize()
            except Exception as e:
                print(f"[Scheduler] 循环异常: {e}")

    def _do_check(self):
        """执行绩效追踪"""
        try:
            from core import performance_tracker
            result = performance_tracker.run_performance_check()
            self._last_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._status["last_check"] = self._last_check
            self._status["total_checks"] += 1
            self._status["total_picks_tracked"] += result.get("updated", 0)
            print(f"[Scheduler] 绩效检查完成: {result}")
        except Exception as e:
            print(f"[Scheduler] 绩效检查失败: {e}")

    def _do_optimize(self):
        """执行策略优化"""
        try:
            from core import strategy_optimizer
            results = strategy_optimizer.optimize_all()
            self._last_optimize = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._status["last_optimize"] = self._last_optimize
            self._status["total_optimizes"] += 1

            success_count = sum(1 for r in results.values() if "error" not in r and "message" not in r)
            print(f"[Scheduler] 优化完成: {success_count}/{len(results)} 个策略")
        except Exception as e:
            print(f"[Scheduler] 优化失败: {e}")

    def _should_optimize(self):
        """判断是否应该触发优化"""
        try:
            from core import db_manager
            # 检查是否有足够的新数据
            conn = db_manager.get_conn()
            c = conn.cursor()

            c.execute("""
                SELECT COUNT(*) FROM pick_performance
                WHERE updated_at > COALESCE(
                    (SELECT MAX(optimize_date) FROM optimization_log), '2000-01-01'
                )
            """)
            count = c.fetchone()[0]
            conn.close()
            return count >= OPTIMIZE_THRESHOLD
        except:
            return False


# 全局单例
_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def start_scheduler():
    """启动调度器（由 web_dashboard.py 调用）"""
    return get_scheduler().start()


def stop_scheduler():
    """停止调度器"""
    s = get_scheduler()
    s.stop()
