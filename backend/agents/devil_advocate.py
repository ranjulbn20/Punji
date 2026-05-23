"""Devil's Advocate Agent — critiques every proposal before it reaches the user."""
from agents.state import PunjiState
from llm import DEVIL_ADVOCATE


async def devil_advocate_node(state: PunjiState, db=None) -> PunjiState:
    proposal = state.get("proposal", {})
    market = state.get("market_context", {})
    allocation = state.get("allocation_report", {})
    goals = state.get("goal_analysis", {}).get("goals", [])

    if not proposal or proposal.get("action") == "hold":
        state["critique"] = {"overall": "not_applicable", "dimensions": {}}
        return state

    import json
    prompt = f"""You are a devil's advocate reviewing a financial recommendation for an Indian investor.

PROPOSAL:
{json.dumps(proposal, indent=2)}

CONTEXT:
Market: {json.dumps(market)}
Current allocation: {json.dumps(allocation.get('allocation', {}))}
Goals: {json.dumps(goals)}

Evaluate the proposal across 6 dimensions. For each, rate: "critical" | "moderate" | "minor" | "not_applicable".
Do NOT fabricate concerns. If no valid objection exists, use "not_applicable".

Return ONLY a JSON object:
{{
  "overall": "critical|moderate|minor|not_applicable",
  "dimensions": {{
    "timing_risk": {{"rating": "...", "concern": "..."}},
    "goal_conflict": {{"rating": "...", "concern": "..."}},
    "tax_implications": {{"rating": "...", "concern": "..."}},
    "simpler_alternative": {{"rating": "...", "concern": "..."}},
    "concentration_risk": {{"rating": "...", "concern": "..."}},
    "liquidity_risk": {{"rating": "...", "concern": "..."}}
  }},
  "strongest_concern": "one sentence summary of the biggest risk"
}}"""

    try:
        critique = await DEVIL_ADVOCATE.generate_json(prompt)
    except Exception:
        critique = {
            "overall": "minor",
            "dimensions": {},
            "strongest_concern": "Unable to generate critique — proceed with caution",
        }

    state["critique"] = critique
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"DevilsAdvocate: overall={critique.get('overall', 'N/A')}. "
        f"{critique.get('strongest_concern', '')}"
    ]
    return state
