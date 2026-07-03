"""
AI 多智能体分析流水线 — 纯 Python 实现

从 TradingAgents 迁移，去除 langchain/langgraph 依赖，
直接使用 DeepSeek SDK + function-calling 实现：

Phase 1: 分析师报告（Market → Sentiment → Fundamentals）
Phase 2: 多空辩论（Bull ⇄ Bear → Research Manager）
Phase 3: 交易决策（Trader）
Phase 4: 风控辩论（Aggressive → Conservative → Neutral → PM）
Phase 5: 最终决策

每个阶段通过 generator yield 事件，供 SSE 实时推送。
"""

import json
import re
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Generator, Optional

from pydantic import BaseModel, Field

# --- 本地导入 ---
try:
    from core.llm_client import LLMClient, get_llm
    from core.ai_analyst_data import (
        get_stock_data,
        get_indicators,
        get_verified_snapshot,
        get_fundamentals,
        get_market_data,
        get_symbol_name,
    )
except ImportError:
    # 兼容直接运行
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.llm_client import LLMClient, get_llm
    from core.ai_analyst_data import (
        get_stock_data,
        get_indicators,
        get_verified_snapshot,
        get_fundamentals,
        get_market_data,
        get_symbol_name,
    )


# ============================================================
#  Pydantic 结构化输出 Schema
# ============================================================

class PortfolioRating(str, Enum):
    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


class SentimentBand(str, Enum):
    BULLISH = "Bullish"
    MILDLY_BULLISH = "Mildly Bullish"
    NEUTRAL = "Neutral"
    MIXED = "Mixed"
    MILDLY_BEARISH = "Mildly Bearish"
    BEARISH = "Bearish"


class SentimentReport(BaseModel):
    overall_band: SentimentBand = Field(description="整体情绪方向")
    overall_score: float = Field(ge=0, le=10, description="情绪评分 0-10")
    confidence: str = Field(description="置信度: low/medium/high")
    narrative: str = Field(description="情绪分析详细报告")


class ResearchPlan(BaseModel):
    recommendation: PortfolioRating = Field(description="投资建议: Buy/Overweight/Hold/Underweight/Sell")
    rationale: str = Field(description="裁决理由，总结辩论关键点")
    strategic_actions: str = Field(description="具体交易执行建议")


class TraderProposal(BaseModel):
    action: TraderAction = Field(description="交易方向: Buy/Hold/Sell")
    reasoning: str = Field(description="交易理由")
    entry_price: Optional[float] = Field(default=None, description="入场价")
    stop_loss: Optional[float] = Field(default=None, description="止损价")
    position_sizing: Optional[str] = Field(default=None, description="仓位建议")


class PortfolioDecision(BaseModel):
    rating: PortfolioRating = Field(description="最终评级")
    executive_summary: str = Field(description="执行摘要: 入场策略、仓位、风险水平、时间周期")
    investment_thesis: str = Field(description="投资论点: 基于分析师辩论的具体证据")
    price_target: Optional[float] = Field(default=None, description="目标价")
    time_horizon: Optional[str] = Field(default=None, description="建议持有周期")


# ============================================================
#  Tool 定义（function-calling 格式）
# ============================================================

TOOLS_MARKET = [
    {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": (
                "一次性获取K线(OHLCV)+全部技术指标(EMA/SMA/RSI/Bollinger/MACD/ATR)。"
                "返回90天K线表格+最后一次技术指标快照。"
                "这是最优先使用的方法，只需调用一次。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码，如 '600519.SS'"},
                    "curr_date": {"type": "string", "description": "分析日期 YYYY-mm-dd"},
                    "look_back_days": {"type": "integer", "description": "回看天数，默认 90"},
                },
                "required": ["symbol", "curr_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "获取股票K线原始数据（仅OHLCV，无指标）。仅在get_market_data失败时备用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                    "start_date": {"type": "string", "description": "起始日期 YYYY-mm-dd"},
                    "end_date": {"type": "string", "description": "结束日期 YYYY-mm-dd"},
                },
                "required": ["symbol", "start_date", "end_date"],
            },
        },
    },
]

TOOLS_FUNDAMENTALS = [
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": "获取公司基本面信息（通达信 finance 接口）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "股票代码"},
                },
                "required": ["symbol"],
            },
        },
    },
]

# Tool 执行映射
TOOL_EXECUTORS = {
    "get_market_data": lambda args: get_market_data(**args),
    "get_stock_data": lambda args: get_stock_data(**args),
    "get_indicators": lambda args: get_indicators(**args),
    "get_verified_snapshot": lambda args: get_verified_snapshot(**args),
    "get_fundamentals": lambda args: get_fundamentals(**args),
}


# ============================================================
#  Agent Prompt 模板
# ============================================================

MARKET_ANALYST_SYSTEM = """你是 A 股市场技术分析师。分析股票走势并给出交易建议。

流程（只需 1 次工具调用）:
1. 调用 get_market_data 一次性获取 K 线 + 全部指标（EMA/SMA/RSI/Bollinger/MACD/ATR）
2. 基于返回数据中的表格和指标快照，撰写详细技术分析报告

报告结构:
- 趋势结构: 基于 EMA 和 SMA 判断短期/中期/长期趋势
- 动量分析: RSI 超买超卖、MACD 金叉死叉
- 波动率: 布林带宽度和位置、ATR 波动水平
- 关键价位: 基于布林带和均线的支撑/阻力位
- 成交量: 量价配合情况
- 综合评估 + FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**

注意:
- 所有数字必须来自工具返回的实际数据，不得编造
- 用中文撰写，精炼专业"""


SENTIMENT_ANALYST_SYSTEM = """你是 A 股市场情绪分析师。你需要基于以下数据源分析市场情绪：

注意：对于 A 股，StockTwits 和 Reddit 数据可能不可用，这是正常的。
请基于可用数据（新闻头条、大盘涨跌比、涨停/跌停数据、宏观事件等）
给出专业的情绪判断。

分析要点:
1. 大盘环境：指数涨跌、成交量变化
2. 行业热度：所属板块近期表现
3. 资金流向：北向资金、主力资金
4. 市场新闻：最近重大事件对情绪的影响
5. 风险提示：政策风险、外部冲击等

输出结构化情绪报告，包含 overall_band、overall_score、confidence 和 narrative。"""


FUNDAMENTALS_ANALYST_SYSTEM = """你是基本面研究员。请对目标股票进行基本面分析。

使用 get_fundamentals 工具获取公司基本信息。
对于返回的数据，分析以下方面：
1. 估值水平：PE、PB是否合理，与同行业对比
2. 市值规模：大盘/中盘/小盘，流动性如何
3. 公司概况：主营业务、行业地位（如果数据可用）
4. 财务健康：ROE、负债率等（如果数据可用）

注意：
- 如果PE/PB数据为"数据不可用"，不要判定为负面，应标注"估值数据暂不可得"
- 不要因为没有完整数据就给出负面评价，应基于已有数据客观分析
- 用中文撰写全面的基本面报告。"""


BULL_RESEARCHER_PROMPT = """你是多方研究员，需要为投资**{symbol}**构建有力论据。

参考以下报告:

市场技术报告: {market_report}

情绪报告: {sentiment_report}

基本面报告: {fundamentals_report}

上次空方论点: {last_bear}

结合以上信息，提出有说服力的多方论点，强调增长潜力、竞争优势和积极指标。
用数据和推理反驳空方的担忧。以对话风格输出。"""


BEAR_RESEARCHER_PROMPT = """你是空方研究员，需要论证**{symbol}**的投资风险。

参考以下报告:

市场技术报告: {market_report}

情绪报告: {sentiment_report}

基本面报告: {fundamentals_report}

上次多方论点: {last_bull}

结合以上信息，提出有说服力的空方论点，强调风险、挑战和负面指标。
用数据和推理反驳多方的乐观假设。以对话风格输出。"""


RESEARCH_MANAGER_PROMPT = """你是研究主管，负责评估本轮多空辩论并给出明确的投资计划。

评级标准:
- Buy: 强烈看多，建议建仓或加仓
- Overweight: 偏多，逐步增加仓位
- Hold: 中性，维持当前仓位
- Underweight: 偏空，逐步减仓
- Sell: 强烈看空，清仓或回避

多空辩论记录:
{debate_history}

请根据辩论质量给出裁决。如果一方论据明显更强，不要犹豫给出明确方向；
只有当双方证据确实势均力敌时才选择 Hold。"""


TRADER_PROMPT = """你是交易员。基于研究主管的投资计划和各分析师报告，制定具体的交易方案。

投资计划: {investment_plan}

请给出: 交易方向(Buy/Hold/Sell)、入场价、止损价、仓位建议。
买卖理由必须基于具体数据分析。"""


AGGRESSIVE_ANALYST_PROMPT = """你是激进风险分析师。评估交易方案的高回报机会，挑战保守观点。

交易方案: {trader_plan}

市场报告: {market_report}
情绪报告: {sentiment_report}
基本面报告: {fundamentals_report}

上次保守方论点: {last_conservative}
上次中性方论点: {last_neutral}

强调潜在上行空间和机会成本，用数据支撑高风险高回报观点。"""


CONSERVATIVE_ANALYST_PROMPT = """你是保守风险分析师。评估交易方案的下行风险，挑战激进假设。

交易方案: {trader_plan}

上次激进方论点: {last_aggressive}
上次中性方论点: {last_neutral}

强调风险因素、最大回撤和最坏情况，用数据支撑保守立场。"""


NEUTRAL_ANALYST_PROMPT = """你是中性风险分析师。平衡激进和保守的观点，提供客观的风险收益评估。

交易方案: {trader_plan}

上次激进方论点: {last_aggressive}
上次保守方论点: {last_conservative}

市场报告: {market_report}

给出平衡的风险收益分析，承认双方论点的合理性，指出关键分歧点。"""


PORTFOLIO_MANAGER_PROMPT = """你是投资组合经理。综合所有分析师和风控团队的辩论，做出最终投资决策。

评级标准: Buy / Overweight / Hold / Underweight / Sell

研究计划: {investment_plan}
交易方案: {trader_plan}

风控辩论记录:
{risk_history}

请给出:
1. 最终评级（从五级中选择）
2. 执行摘要（2-4 句，含入场策略、仓位、风险水平、时间周期）
3. 投资论点（详细论述，引用具体证据）
4. 目标价和建议持有周期

要果断，将每个结论锚定在具体证据上。用中文输出。"""


# ============================================================
#  Agent 执行函数
# ============================================================

def _execute_tool_call(llm: LLMClient, messages: list, tools: list, max_rounds: int = 10) -> str:
    """执行 tool-calling 循环，直到 LLM 不再调用工具或达到最大轮次"""
    for _ in range(max_rounds):
        content, tool_calls, usage = llm.chat_with_tools(messages, tools)

        if not tool_calls:
            return content

        # 添加助手消息
        assistant_msg = {"role": "assistant", "content": content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        # 执行每个工具调用
        for tc in tool_calls:
            executor = TOOL_EXECUTORS.get(tc["name"])
            if executor:
                result = executor(tc["arguments"])
            else:
                result = f"ERROR: 未知工具 '{tc['name']}'"

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result[:8000],
            })

    return "ERROR: 达到最大工具调用轮次"


def _run_market_analyst(llm: LLMClient, symbol: str, curr_date: str, name: str) -> str:
    """市场分析师 — 只需 1 次 get_market_data 调用"""
    messages = [
        {"role": "system", "content": MARKET_ANALYST_SYSTEM},
        {"role": "user", "content": (
            f"请对 {name}({symbol}) 进行全面技术分析。\n"
            f"分析日期: {curr_date}\n"
            f"先调用 get_market_data 获取数据，然后撰写完整报告。用中文。"
        )},
    ]
    return _execute_tool_call(llm, messages, TOOLS_MARKET, max_rounds=2)


def _run_sentiment_analyst(llm: LLMClient, symbol: str, curr_date: str, name: str) -> str:
    """情绪分析师 — 纯 LLM 分析（无工具调用）"""
    start_date = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")

    try:
        news_text = get_stock_data(symbol, start_date, curr_date)[:3000]
    except Exception:
        news_text = "数据不可用"

    messages = [
        {"role": "system", "content": SENTIMENT_ANALYST_SYSTEM},
        {"role": "user", "content": (
            f"请对 {name}({symbol}) 进行情绪分析。分析日期: {curr_date}。\n\n"
            f"近期股价数据（供参考）:\n{news_text}\n\n"
            f"请给出结构化情绪报告: overall_band(NumericScale: Bullish/MildlyBullish/Neutral/Mixed/MildlyBearish/Bearish), overall_score(0-10), confidence(low/medium/high), narrative。"
            f"注意：A股没有 StockTwits/Reddit，请基于技术面和市场环境判断。"
            f"用中文撰写。"
        )},
    ]
    return llm.structured_output(messages, SentimentReport)[0]


def _run_fundamentals_analyst(llm: LLMClient, symbol: str, curr_date: str, name: str) -> str:
    """基本面分析师 — 带工具调用"""
    messages = [
        {"role": "system", "content": FUNDAMENTALS_ANALYST_SYSTEM},
        {"role": "user", "content": (
            f"请对 {name}({symbol}) 进行基本面分析。分析日期: {curr_date}。\n"
            f"使用 get_fundamentals 获取公司信息，撰写全面报告。用中文撰写。"
        )},
    ]
    return _execute_tool_call(llm, messages, TOOLS_FUNDAMENTALS)


def _run_bull_researcher(llm: LLMClient, symbol: str, name: str, reports: dict, last_bear: str) -> str:
    """多方研究员"""
    prompt = BULL_RESEARCHER_PROMPT.format(
        symbol=f"{name}({symbol})",
        market_report=reports.get("market", "暂无")[:5000],
        sentiment_report=str(reports.get("sentiment", "暂无"))[:3000],
        fundamentals_report=reports.get("fundamentals", "暂无")[:3000],
        last_bear=last_bear or "（首轮发言，无空方论点）",
    )
    messages = [{"role": "user", "content": prompt}]
    return llm.chat(messages)[0]


def _run_bear_researcher(llm: LLMClient, symbol: str, name: str, reports: dict, last_bull: str) -> str:
    """空方研究员"""
    prompt = BEAR_RESEARCHER_PROMPT.format(
        symbol=f"{name}({symbol})",
        market_report=reports.get("market", "暂无")[:5000],
        sentiment_report=str(reports.get("sentiment", "暂无"))[:3000],
        fundamentals_report=reports.get("fundamentals", "暂无")[:3000],
        last_bull=last_bull or "（首轮发言，无多方论点）",
    )
    messages = [{"role": "user", "content": prompt}]
    return llm.chat(messages)[0]


def _run_research_manager(llm: LLMClient, debate_history: str) -> ResearchPlan:
    """研究主管裁决"""
    prompt = RESEARCH_MANAGER_PROMPT.format(debate_history=debate_history[-6000:])
    messages = [{"role": "user", "content": prompt}]
    result = llm.structured_output(messages, ResearchPlan)[0]
    if isinstance(result, str):
        return ResearchPlan(recommendation="Hold", rationale=result, strategic_actions="N/A")
    return result


def _run_trader(llm: LLMClient, symbol: str, name: str, investment_plan: str) -> TraderProposal:
    """交易员"""
    prompt = TRADER_PROMPT.format(investment_plan=investment_plan)
    messages = [
        {"role": "system", "content": f"你正在为 {name}({symbol}) 制定交易方案。用中文。"},
        {"role": "user", "content": prompt},
    ]
    result = llm.structured_output(messages, TraderProposal)[0]
    if isinstance(result, str):
        return TraderProposal(action="Hold", reasoning=result)
    return result


def _run_aggressive_analyst(llm: LLMClient, reports: dict, trader_plan: str,
                             last_conservative: str, last_neutral: str) -> str:
    prompt = AGGRESSIVE_ANALYST_PROMPT.format(
        trader_plan=trader_plan[:500],
        market_report=reports.get("market", "暂无")[:1000],
        sentiment_report=str(reports.get("sentiment", "暂无"))[:800],
        fundamentals_report=reports.get("fundamentals", "暂无")[:1000],
        last_conservative=last_conservative[-500:] if last_conservative else "（首轮）",
        last_neutral=last_neutral[-500:] if last_neutral else "（首轮）",
    )
    return llm.chat([{"role": "user", "content": prompt}])[0]


def _run_conservative_analyst(llm: LLMClient, reports: dict, trader_plan: str,
                               last_aggressive: str, last_neutral: str) -> str:
    prompt = CONSERVATIVE_ANALYST_PROMPT.format(
        trader_plan=trader_plan[:500],
        last_aggressive=last_aggressive[-500:] if last_aggressive else "（首轮）",
        last_neutral=last_neutral[-500:] if last_neutral else "（首轮）",
    )
    messages = [
        {"role": "system", "content": f"市场报告: {reports.get('market','')[:1000]}"},
        {"role": "user", "content": prompt},
    ]
    return llm.chat(messages)[0]


def _run_neutral_analyst(llm: LLMClient, reports: dict, trader_plan: str,
                          last_aggressive: str, last_conservative: str) -> str:
    prompt = NEUTRAL_ANALYST_PROMPT.format(
        trader_plan=trader_plan[:500],
        last_aggressive=last_aggressive[-500:] if last_aggressive else "（首轮）",
        last_conservative=last_conservative[-500:] if last_conservative else "（首轮）",
        market_report=reports.get("market", "暂无")[:1000],
    )
    return llm.chat([{"role": "user", "content": prompt}])[0]


def _run_portfolio_manager(llm: LLMClient, symbol: str, name: str,
                           investment_plan: str, trader_plan: str,
                           risk_history: str) -> PortfolioDecision:
    prompt = PORTFOLIO_MANAGER_PROMPT.format(
        investment_plan=investment_plan,
        trader_plan=trader_plan,
        risk_history=risk_history[-5000:],
    )
    messages = [
        {"role": "system", "content": f"你是投资组合经理，为 {name}({symbol}) 做最终决策。用中文输出。"},
        {"role": "user", "content": prompt},
    ]
    result = llm.structured_output(messages, PortfolioDecision)[0]
    if isinstance(result, str):
        return PortfolioDecision(
            rating="Hold",
            executive_summary="无法解析结构化输出",
            investment_thesis=result,
        )
    return result


# ============================================================
#  主流水线 — Generator
# ============================================================

STAGES = [
    {"id": "market", "label": "市场技术分析", "progress_start": 5, "progress_end": 25, "icon": "chart"},
    {"id": "sentiment", "label": "市场情绪分析", "progress_start": 25, "progress_end": 35, "icon": "mood"},
    {"id": "fundamentals", "label": "基本面分析", "progress_start": 35, "progress_end": 45, "icon": "finance"},
    {"id": "debate", "label": "多空辩论", "progress_start": 45, "progress_end": 65, "icon": "debate"},
    {"id": "trader", "label": "交易决策", "progress_start": 65, "progress_end": 75, "icon": "trade"},
    {"id": "risk", "label": "风控辩论", "progress_start": 75, "progress_end": 90, "icon": "risk"},
    {"id": "pm", "label": "最终决策", "progress_start": 90, "progress_end": 100, "icon": "gavel"},
]


def run_analysis_pipeline(
    symbol: str,
    trade_date: str,
    model: Optional[str] = None,
    max_debate_rounds: int = 1,
    max_risk_rounds: int = 1,
) -> Generator[dict, None, dict]:
    """运行完整的多智能体分析流水线, 通过 generator yield 每个阶段的事件。

    Yields:
        {"type": "stage_start", "stage": "...", "label": "...", "progress": N, "icon": "..."}
        {"type": "stage_done", "stage": "...", "report": "...", "progress": N}
        {"type": "stage_chunk", "stage": "...", "text": "..."}
        {"type": "all_done", "result": {...}}
    """
    llm = LLMClient(model=model) if model else get_llm()
    code = symbol.split(".")[0] if "." in symbol else symbol
    name = get_symbol_name(code)
    run_id = uuid.uuid4().hex[:12]

    reports = {}
    start_time = time.time()

    # ---- Phase 1: 分析师报告 (顺序) ----

    # Market Analyst — 优化：1 次 get_market_data 调用，~10s vs 旧版 80s+
    stage = STAGES[0]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}
    yield {"type": "stage_chunk", "stage": "market",
           "text": "🔍 正在获取行情数据 (K线+EMA/SMA/RSI/MACD/布林/ATR)...", "heading": False}
    try:
        market_report = _run_market_analyst(llm, symbol, trade_date, name)
        reports["market"] = market_report
        yield {"type": "stage_chunk", "stage": "market",
               "text": "✅ 数据已获取，分析报告生成完毕", "heading": False}
        yield {"type": "stage_done", "stage": "market",
               "report": market_report, "progress": stage["progress_end"]}
    except Exception as e:
        reports["market"] = f"分析失败: {e}"
        yield {"type": "stage_done", "stage": "market",
               "report": reports["market"], "progress": stage["progress_end"]}

    # Sentiment Analyst
    stage = STAGES[1]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}
    yield {"type": "stage_chunk", "stage": "sentiment",
           "text": "正在分析市场情绪数据...", "heading": False}
    try:
        sentiment_result = _run_sentiment_analyst(llm, symbol, trade_date, name)
        if isinstance(sentiment_result, SentimentReport):
            reports["sentiment"] = (
                f"**整体情绪**: {sentiment_result.overall_band.value} "
                f"(评分: {sentiment_result.overall_score:.1f}/10)\n"
                f"**置信度**: {sentiment_result.confidence}\n\n"
                f"{sentiment_result.narrative}"
            )
        else:
            reports["sentiment"] = str(sentiment_result)
        yield {"type": "stage_done", "stage": "sentiment",
               "report": reports["sentiment"], "progress": stage["progress_end"]}
    except Exception as e:
        reports["sentiment"] = f"分析失败: {e}"
        yield {"type": "stage_done", "stage": "sentiment",
               "report": reports["sentiment"], "progress": stage["progress_end"]}

    # Fundamentals Analyst
    stage = STAGES[2]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}
    yield {"type": "stage_chunk", "stage": "fundamentals",
           "text": "正在获取基本面数据...", "heading": False}
    try:
        fundamentals_report = _run_fundamentals_analyst(llm, symbol, trade_date, name)
        reports["fundamentals"] = fundamentals_report
        yield {"type": "stage_done", "stage": "fundamentals",
               "report": fundamentals_report, "progress": stage["progress_end"]}
    except Exception as e:
        reports["fundamentals"] = f"分析失败: {e}"
        yield {"type": "stage_done", "stage": "fundamentals",
               "report": reports["fundamentals"], "progress": stage["progress_end"]}

    # ---- Phase 2: 多空辩论 ----
    stage = STAGES[3]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}

    debate_history = ""
    bull_response = ""
    bear_response = ""
    bull_history = ""
    bear_history = ""

    for round_num in range(max_debate_rounds):
        yield {"type": "stage_chunk", "stage": "debate",
               "text": f"**多方研究员** (第{round_num+1}轮) ", "heading": True, "role": "bull"}
        bull_response = _run_bull_researcher(llm, symbol, name, reports, bear_response)
        bull_history += f"\n{bull_response}\n"
        debate_history += f"\nBull: {bull_response}\n"
        yield {"type": "stage_chunk", "stage": "debate", "text": bull_response, "role": "bull"}

        yield {"type": "stage_chunk", "stage": "debate",
               "text": f"**空方研究员** (第{round_num+1}轮) ", "heading": True, "role": "bear"}
        bear_response = _run_bear_researcher(llm, symbol, name, reports, bull_response)
        bear_history += f"\n{bear_response}\n"
        debate_history += f"\nBear: {bear_response}\n"
        yield {"type": "stage_chunk", "stage": "debate", "text": bear_response, "role": "bear"}

    # Research Manager 裁决
    yield {"type": "stage_chunk", "stage": "debate",
           "text": "**研究主管裁决**:\n", "heading": True, "role": "manager"}
    research_plan = _run_research_manager(llm, debate_history)
    investment_plan = (
        f"**建议**: {research_plan.recommendation.value}\n\n"
        f"**理由**: {research_plan.rationale}\n\n"
        f"**执行建议**: {research_plan.strategic_actions}"
    )
    yield {"type": "stage_chunk", "stage": "debate", "text": investment_plan}

    # 将完整辩论历史附加到报告中
    full_debate_report = (
        f"### 多方论点\n{bull_history}\n\n"
        f"### 空方论点\n{bear_history}\n\n"
        f"### 研究主管裁决\n{investment_plan}"
    )

    yield {"type": "stage_done", "stage": "debate",
           "report": full_debate_report, "progress": stage["progress_end"],
           "data": {
               "rating": research_plan.recommendation.value,
               "bull_history": bull_history,
               "bear_history": bear_history,
               "debate_history": debate_history,
               "investment_plan": investment_plan,
           }}

    # ---- Phase 3: 交易决策 ----
    stage = STAGES[4]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}
    yield {"type": "stage_chunk", "stage": "trader",
           "text": "正在制定交易方案...", "heading": False}

    trader_plan = _run_trader(llm, symbol, name, investment_plan)
    trader_text = (
        f"**交易方向**: {trader_plan.action.value}\n\n"
        f"**理由**: {trader_plan.reasoning}\n"
        + (f"\n**入场价**: {trader_plan.entry_price}\n" if trader_plan.entry_price else "")
        + (f"\n**止损价**: {trader_plan.stop_loss}\n" if trader_plan.stop_loss else "")
        + (f"\n**仓位**: {trader_plan.position_sizing}\n" if trader_plan.position_sizing else "")
    )

    yield {"type": "stage_chunk", "stage": "trader", "text": trader_text}
    yield {"type": "stage_done", "stage": "trader",
           "report": trader_text, "progress": stage["progress_end"],
           "data": {
               "action": trader_plan.action.value,
               "entry_price": trader_plan.entry_price,
               "stop_loss": trader_plan.stop_loss,
           }}

    # ---- Phase 4: 风控辩论 ----
    stage = STAGES[5]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}

    risk_history = ""
    agg_response = ""
    con_response = ""
    neu_response = ""
    agg_hist = ""
    con_hist = ""
    neu_hist = ""

    for round_num in range(max_risk_rounds):
        yield {"type": "stage_chunk", "stage": "risk",
               "text": f"**激进分析师** (第{round_num+1}轮):\n", "role": "aggressive"}
        agg_response = _run_aggressive_analyst(llm, reports, trader_text,
                                                con_response, neu_response)
        agg_hist += f"\n{agg_response}\n"
        risk_history += f"\nAggressive: {agg_response}\n"
        yield {"type": "stage_chunk", "stage": "risk", "text": agg_response, "role": "aggressive"}

        yield {"type": "stage_chunk", "stage": "risk",
               "text": f"**保守分析师** (第{round_num+1}轮):\n", "role": "conservative"}
        con_response = _run_conservative_analyst(llm, reports, trader_text,
                                                  agg_response, neu_response)
        con_hist += f"\n{con_response}\n"
        risk_history += f"\nConservative: {con_response}\n"
        yield {"type": "stage_chunk", "stage": "risk", "text": con_response, "role": "conservative"}

        yield {"type": "stage_chunk", "stage": "risk",
               "text": f"**中性分析师** (第{round_num+1}轮):\n", "role": "neutral"}
        neu_response = _run_neutral_analyst(llm, reports, trader_text,
                                             agg_response, con_response)
        neu_hist += f"\n{neu_response}\n"
        risk_history += f"\nNeutral: {neu_response}\n"
        yield {"type": "stage_chunk", "stage": "risk", "text": neu_response, "role": "neutral"}

    yield {"type": "stage_done", "stage": "risk",
           "report": risk_history, "progress": stage["progress_end"],
           "data": {
               "aggressive_history": agg_hist,
               "conservative_history": con_hist,
               "neutral_history": neu_hist,
               "risk_history": risk_history,
           }}

    # ---- Phase 5: 最终决策 ----
    stage = STAGES[6]
    yield {"type": "stage_start", "stage": stage["id"], "label": stage["label"],
           "progress": stage["progress_start"], "icon": stage["icon"]}
    yield {"type": "stage_chunk", "stage": "pm",
           "text": "正在综合所有分析结果做最终决策...", "heading": False}

    portfolio_decision = _run_portfolio_manager(
        llm, symbol, name, investment_plan, trader_text, risk_history
    )

    final_text = (
        f"**最终评级**: {portfolio_decision.rating.value}\n\n"
        f"**执行摘要**: {portfolio_decision.executive_summary}\n\n"
        f"**投资论点**: {portfolio_decision.investment_thesis}\n"
        + (f"\n**目标价**: {portfolio_decision.price_target}\n" if portfolio_decision.price_target else "")
        + (f"\n**建议周期**: {portfolio_decision.time_horizon}\n" if portfolio_decision.time_horizon else "")
    )

    yield {"type": "stage_chunk", "stage": "pm", "text": final_text}

    elapsed = time.time() - start_time
    result = {
        "run_id": run_id,
        "symbol": symbol,
        "code": code,
        "name": name,
        "trade_date": trade_date,
        "rating": portfolio_decision.rating.value,
        "summary": portfolio_decision.executive_summary,
        "thesis": portfolio_decision.investment_thesis,
        "price_target": portfolio_decision.price_target,
        "time_horizon": portfolio_decision.time_horizon,
        "elapsed_seconds": round(elapsed, 1),
        "reports": reports,
        "investment_plan": investment_plan,
        "trader_plan": trader_text,
        "debate_history": debate_history,
        "risk_history": risk_history,
        "bull_history": bull_history,
        "bear_history": bear_history,
        "final_decision": final_text,
    }

    yield {"type": "all_done", "result": result}
    return result
