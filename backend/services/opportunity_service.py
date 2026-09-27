"""
Phase 3 — routes a high-conviction, company-specific signal into a concrete
recommendation (RECOMMENDATION role), critiqued by a devil's advocate
(DEVIL_ADVOCATE role). Detection stays separate from decision: the
informational market_event alert (agents/proactive_alert.py) always fires
on its own; this only ever produces an *additional*, distinct alert when a
signal clears a meaningfully higher bar than "pay attention to this".

Reuses the same LLM roles as the chat pipeline's recommendation_node /
devil_advocate_node, but with a prompt scoped to the one flagged holding and
its signal evidence — a signal about stock X should never come back
recommending stock Y, which the chat pipeline's portfolio-wide prompt could.
"""
import json
from llm import RECOMMENDATION, DEVIL_ADVOCATE

# Meaningfully stricter than the plain informational alert's bar — a
# recommendation carries more implied authority than "pay attention to this".
OPPORTUNITY_MIN_CONFIDENCE = 0.8


def is_opportunity_worthy(signal: dict) -> bool:
    return (
        signal.get("market_context") == "company_specific"
        and signal.get("severity") == "high"
        and signal.get("confidence", 0) >= OPPORTUNITY_MIN_CONFIDENCE
        and signal.get("direction") in ("positive", "negative")
    )


async def generate_opportunity(holding, signal: dict, risk_profile: dict | None) -> dict | None:
    """
    Returns {"proposal": ..., "critique": ...}, or None if the recommendation
    came back "hold" (nothing actionable to surface) or an LLM call failed.
    """
    news = signal.get("news") or {}
    evidence_lines = "\n".join(f"- {e}" for e in signal.get("evidence", []))
    news_line = f"\n- News: {news['headline']} — {news.get('reason', '')}" if news else ""

    prompt = f"""You are Punji, an autonomous personal finance agent for Indian investors.

A monitoring signal flagged {holding.display_name} (NSE: {holding.symbol}) as a {signal['direction']}, company-specific event — not a broad market/sector move.

Evidence:
{evidence_lines}{news_line}

Current position: {float(holding.quantity):.2f} shares, invested ₹{float(holding.invested_amount):,.0f}, current value ₹{float(holding.current_value):,.0f}.
Risk profile: {json.dumps(risk_profile) if risk_profile else "not set"}

Generate a SPECIFIC, ACTIONABLE proposal for THIS holding only — never suggest a different stock. Return ONLY a JSON object:
{{
  "action": "buy|sell|trim|hold",
  "instrument": "{holding.display_name}",
  "amount_inr": <integer rupee amount, 0 if action is hold>,
  "timeline": "immediate|this_week|this_month",
  "reasoning": "why, referencing the evidence above",
  "expected_outcome": "what this achieves",
  "tax_note": "any STCG/LTCG implications"
}}

Rules:
- If the evidence doesn't genuinely support action beyond continuing to hold, use action="hold".
- Amount must be a specific number, not a range."""

    try:
        proposal = await RECOMMENDATION.generate_json(prompt)
    except Exception:
        return None

    if proposal.get("action") == "hold":
        return None

    critique_prompt = f"""You are a devil's advocate reviewing this financial recommendation for an Indian investor.
Your job is to challenge the EVIDENCE behind the proposal, not just agree or disagree with its conclusion.

PROPOSAL:
{json.dumps(proposal, indent=2)}

CONTEXT:
Holding: {holding.display_name}, current position value ₹{float(holding.current_value):,.0f} ({signal.get("portfolio_weight_pct", 0):.1f}% of portfolio)
Signal evidence: {'; '.join(signal.get("evidence", []))}
Market context: {signal.get("market_context", "unknown")} (is this move specific to this company, or shared with its sector/market?)
Risk profile: {json.dumps(risk_profile) if risk_profile else "not set"}

Evaluate the proposal across 6 dimensions. For each, rate: "critical" | "moderate" | "minor" | "not_applicable".
Do NOT fabricate concerns. If no valid objection exists, use "not_applicable".

Return ONLY a JSON object:
{{
  "overall": "critical|moderate|minor|not_applicable",
  "dimensions": {{
    "priced_in": {{"rating": "...", "concern": "is the market likely to have already priced this event in?"}},
    "temporary_vs_structural": {{"rating": "...", "concern": "is this a one-off event or a structural deterioration?"}},
    "company_vs_sector": {{"rating": "...", "concern": "could this reverse if it's actually sector/market-wide despite being flagged company-specific?"}},
    "position_size": {{"rating": "...", "concern": "does the position size actually justify acting, or is it too small/large to matter at this scale?"}},
    "thesis_impact": {{"rating": "...", "concern": "does this evidence genuinely change the investment case, or is it noise?"}},
    "alternative_action": {{"rating": "...", "concern": "would a less aggressive action (e.g. monitor, partial trim, stop-loss) achieve the same goal with less downside?"}}
  }},
  "strongest_concern": "one sentence summary of the biggest reason to doubt this proposal"
}}"""

    try:
        critique = await DEVIL_ADVOCATE.generate_json(critique_prompt)
    except Exception:
        critique = {
            "overall": "minor",
            "dimensions": {},
            "strongest_concern": "Unable to generate critique — proceed with caution",
        }

    return {"proposal": proposal, "critique": critique}
