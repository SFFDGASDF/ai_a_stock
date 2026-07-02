"""
AI 多智能体分析 API — 基于 SSE 的实时流式端点

POST /api/ai-analyze → SSE 事件流（stage_start / stage_chunk / stage_done / all_done）
GET  /api/ai-history  → 历史分析记录
GET  /api/ai-report/<run_id> → 单次分析完整报告
"""

import json
import sys
import os
import uuid
import time
import threading
from datetime import datetime

from flask import Blueprint, Response, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ai_analyst_pipeline import run_analysis_pipeline
from core.llm_client import get_llm
import core.db_manager as db_manager

ai_bp = Blueprint("ai", __name__, url_prefix="/api")


def _sse(data: dict) -> str:
    """将字典序列化为 SSE data 行"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@ai_bp.route("/ai-analyze", methods=["POST"])
def api_ai_analyze():
    """启动 AI 多智能体分析，返回 SSE 事件流"""
    body = request.get_json(silent=True) or {}
    symbol = (body.get("symbol") or "").strip()
    trade_date = (body.get("date") or body.get("trade_date") or "").strip()

    if not symbol:
        return jsonify({"error": "请提供股票代码 symbol"}), 400
    if not trade_date:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    # 验证 API key
    try:
        llm = get_llm()
        if not llm.api_key:
            return jsonify({"error": "未配置 DEEPSEEK_API_KEY，请在 .env 中设置"}), 500
    except Exception as e:
        return jsonify({"error": f"LLM 初始化失败: {e}"}), 500

    max_debate = int(body.get("max_debate_rounds") or 1)
    max_risk = int(body.get("max_risk_rounds") or 1)
    model = body.get("model") or None

    def generate():
        run_id = uuid.uuid4().hex[:12]
        stage_reports = {}
        final_result = None
        start_ts = time.time()

        try:
            for event in run_analysis_pipeline(
                symbol=symbol,
                trade_date=trade_date,
                model=model,
                max_debate_rounds=max_debate,
                max_risk_rounds=max_risk,
            ):
                etype = event.get("type", "")

                if etype == "stage_start":
                    yield _sse(event)

                elif etype == "stage_chunk":
                    # 流式 chunk 保持紧凑
                    yield _sse(event)

                elif etype == "stage_done":
                    stage = event.get("stage", "")
                    report = event.get("report", "")
                    stage_reports[stage] = report
                    yield _sse(event)

                elif etype == "all_done":
                    final_result = event.get("result", {})
                    yield _sse(event)

            # ---- 保存到数据库 ----
            if final_result:
                elapsed = round(time.time() - start_ts, 1)
                try:
                    db_manager.save_ai_run(
                        run_id=final_result.get("run_id", run_id),
                        symbol=symbol,
                        name=final_result.get("name", ""),
                        trade_date=trade_date,
                        rating=final_result.get("rating", ""),
                        summary=final_result.get("summary", ""),
                        result_json=final_result,
                        stages=stage_reports,
                        elapsed_seconds=elapsed,
                    )
                except Exception as e:
                    print(f"[AI-API] 保存失败: {e}", flush=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse({"type": "error", "msg": str(e)})

    return Response(
        generate(),
        mimetype="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@ai_bp.route("/ai-history", methods=["GET"])
def api_ai_history():
    """获取历史 AI 分析记录"""
    limit = int(request.args.get("limit", 20))
    try:
        rows = db_manager.get_ai_runs(limit=limit)
        return jsonify({"history": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/ai-latest-by-codes", methods=["POST"])
def api_ai_latest_by_codes():
    """批量查询多只股票的最新 AI 分析结果。
    POST body: {"codes": ["600519", "000858"]}
    返回: {"results": {"600519": {"rating":"Buy","summary":"...","trade_date":"...","run_id":"...","name":"..."}, ...}}
    """
    body = request.get_json(silent=True) or {}
    codes = body.get("codes", [])
    if not codes or not isinstance(codes, list):
        return jsonify({"error": "请提供 codes 数组"}), 400
    try:
        results = db_manager.get_ai_latest_by_codes(codes)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/ai-report/<run_id>", methods=["GET"])
def api_ai_report(run_id):
    """获取单次 AI 分析完整报告"""
    try:
        report = db_manager.get_ai_report(run_id)
        if not report:
            return jsonify({"error": "报告不存在"}), 404
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
