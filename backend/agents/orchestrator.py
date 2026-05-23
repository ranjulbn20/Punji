"""
Orchestrator Agent — detects intent, routes pipeline, synthesises final response.
"""
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.state import PunjiState
from agents.memory import search_memories, save_memory
from models import RiskProfile, Goal
from llm import ORCHESTRATOR

INTENT_ROUTING = {
    "portfolio_overview": ["portfolio_analyser", "concentration_risk", "respond"],
    "portfolio_advice":   ["portfolio_analyser", "market_intelligence", "recommendation", "devil_advocate", "synthesise"],
    "rebalancing":        ["portfolio_analyser", "market_intelligence", "recommendation", "devil_advocate", "synthesise"],
    "goal_check":         ["goal_tracker", "portfolio_analyser", "respond"],
    "tax_query":          ["portfolio_analyser", "respond"],
    "stock_question":     ["market_intelligence", "concentration_risk", "respond"],
    "news_query":         ["news_intelligence", "respond"],
    "fd_advice":          ["portfolio_analyser", "market_intelligence", "recommendation", "respond"],
    "general_finance":    ["market_intelligence", "respond"],
}


async def detect_intent(query: str) -> str:
    if not query.strip():
        return "portfolio_overview"

    prompt = f"""Classify this user query into one of these intents:
portfolio_overview | portfolio_advice | rebalancing | goal_check | tax_query |
stock_question | news_query | fd_advice | general_finance

Query: {query}

Reply with ONLY the intent string, nothing else."""

    try:
        response = await ORCHESTRATOR.generate(prompt, temperature=0.1)
        intent = response.content.strip().lower()
        return intent if intent in INTENT_ROUTING else "portfolio_overview"
    except Exception:
        return "portfolio_overview"


async def load_user_context(state: PunjiState, db: AsyncSession) -> PunjiState:
    user_id = state["user_id"]
    uid = uuid.UUID(user_id)

    rp_result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == uid))
    rp = rp_result.scalar_one_or_none()
    if rp:
        state["risk_profile"] = {
            "risk_category": rp.risk_category,
            "risk_score": rp.risk_score,
            "target_equity_pct": float(rp.target_equity_pct or 0),
            "target_debt_pct": float(rp.target_debt_pct or 0),
            "target_gold_pct": float(rp.target_gold_pct or 0),
        }

    goals_result = await db.execute(select(Goal).where(Goal.user_id == uid, Goal.is_active == True))
    goals = goals_result.scalars().all()
    state["active_goals"] = [
        {"id": str(g.id), "name": g.name, "target_amount": g.target_amount}
        for g in goals
    ]

    query = state.get("user_query", "")
    state["agent_memories"] = await search_memories(user_id, query, db)

    return state


async def synthesise_response(state: PunjiState) -> str:
    proposal = state.get("proposal", {})
    critique = state.get("critique", {})
    allocation = state.get("allocation_report", {})
    market = state.get("market_context", {})
    goal_analysis = state.get("goal_analysis", {})
    memories = state.get("agent_memories", [])
    query = state.get("user_query", "")

    critique_severity = critique.get("overall", "not_applicable") if critique else "not_applicable"

    synthesis_instruction = {
        "minor":          "Adopt the proposal. Acknowledge the critique in one sentence.",
        "moderate":       "Moderate the proposal (reduce amount or add a condition). Give the critique equal weight.",
        "critical":       "Significantly revise or recommend holding action. Give the critique equal or greater weight.",
        "not_applicable": "Present the proposal as-is.",
    }.get(critique_severity, "Present the proposal as-is.")

    user_memories = "\n".join(f"- {m['content']}" for m in memories[:3]) if memories else ""

    prompt = f"""You are Punji, an autonomous personal finance agent for Indian investors.

User question: {query}

Portfolio summary: {json.dumps(allocation.get('allocation', {}), default=str)}
Market context: {market.get('narrative', '') if market else ''}
Goals: {json.dumps(goal_analysis.get('goals', []), default=str) if goal_analysis else '[]'}
What you know about this user: {user_memories}

Proposal: {json.dumps(proposal, default=str) if proposal else 'None'}
Critique (severity: {critique_severity}): {critique.get('strongest_concern', '') if critique else ''}
Synthesis instruction: {synthesis_instruction}

Write a clear, helpful response in 150-250 words. Be specific — reference actual numbers from the data above.
End with: "This is not financial advice — always consult a SEBI-registered advisor for personalised guidance." """

    response = await ORCHESTRATOR.generate(prompt, temperature=0.3)
    return response.content


async def run_orchestrator(
    user_id: str,
    query: str,
    db: AsyncSession,
    run_type: str = "conversational",
    conversation_id: str | None = None,
) -> PunjiState:
    state: PunjiState = {
        "user_id": user_id,
        "user_query": query,
        "run_type": run_type,
        "conversation_id": conversation_id,
        "reasoning_trace": [],
        "news_alerts": [],
        "new_memories": [],
        "alerts_to_create": [],
        "errors": [],
        "active_goals": [],
        "agent_memories": [],
        "current_agent": "orchestrator",
    }

    state = await load_user_context(state, db)

    intent = await detect_intent(query)
    state["intent"] = intent
    state["reasoning_trace"].append(f"Orchestrator: intent={intent}")

    pipeline = INTENT_ROUTING.get(intent, ["respond"])

    for step in pipeline:
        state["current_agent"] = step

        if step == "portfolio_analyser":
            from agents.portfolio_analyser import portfolio_analyser_node
            state = await portfolio_analyser_node(state, db)

        elif step == "market_intelligence":
            from agents.market_intelligence import market_intelligence_node
            state = await market_intelligence_node(state, db)

        elif step == "goal_tracker":
            from agents.goal_tracker import goal_tracker_node
            state = await goal_tracker_node(state, db)

        elif step == "recommendation":
            from agents.recommendation import recommendation_node
            state = await recommendation_node(state, db)

        elif step == "devil_advocate":
            from agents.devil_advocate import devil_advocate_node
            state = await devil_advocate_node(state, db)

        elif step == "news_intelligence":
            from agents.news_intelligence import news_intelligence_node
            state = await news_intelligence_node(state, db)

        elif step == "concentration_risk":
            pass  # already computed by portfolio_analyser

        elif step in ("respond", "synthesise"):
            state["final_response"] = await synthesise_response(state)

    if not state.get("final_response"):
        state["final_response"] = await synthesise_response(state)

    if query and state.get("final_response"):
        await save_memory(
            user_id,
            "conversation_summary",
            f"User asked: {query[:100]}. Key insight: {state['final_response'][:150]}",
            db,
            confidence=0.8,
        )

    return state
