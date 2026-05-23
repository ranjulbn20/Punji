"""Market Intelligence Agent — fetches macro context and narrates it."""
from agents.state import PunjiState
from services.market_service import get_macro_data
from llm import MARKET_INTELLIGENCE


async def market_intelligence_node(state: PunjiState, db=None) -> PunjiState:
    macro = await get_macro_data()

    prompt = f"""Summarise the current Indian market context in 2-3 sentences for a portfolio advisor.
Nifty 50: {macro.get('nifty50_level', 'N/A')}
Nifty P/E: {macro.get('nifty50_pe', 'N/A')}
RBI Repo Rate: {macro.get('repo_rate', 6.5)}%

Be factual and concise. No recommendations — just context."""

    try:
        response = await MARKET_INTELLIGENCE.generate(prompt)
        narrative = response.content
    except Exception:
        narrative = f"Nifty 50 at {macro.get('nifty50_level', 'N/A')}. RBI repo rate at {macro.get('repo_rate', 6.5)}%."

    state["market_context"] = {**macro, "narrative": narrative}
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"MarketIntelligence: {narrative[:100]}..."
    ]
    return state
