"""Recommendation Agent — concrete actionable proposals."""
import json
from agents.state import PunjiState
from llm import RECOMMENDATION


async def recommendation_node(state: PunjiState, db=None) -> PunjiState:
    risk_profile = state.get("risk_profile", {})
    allocation = state.get("allocation_report", {})
    market = state.get("market_context", {})
    memories = state.get("agent_memories", [])
    query = state.get("user_query", "")

    memories_text = "\n".join(f"- {m['content']}" for m in memories) if memories else "None"

    prompt = f"""You are Punji, an autonomous personal finance agent for Indian investors.

User query: {query}

Portfolio state:
{json.dumps(allocation, indent=2)}

Market context: {market.get('narrative', '')}

Risk profile: {json.dumps(risk_profile)}

What you know about this user:
{memories_text}

Generate a SPECIFIC, ACTIONABLE proposal. Return ONLY a JSON object with these exact fields:
{{
  "action": "buy|sell|hold|switch|rebalance",
  "instrument": "specific fund name or stock ticker — never a category",
  "amount_inr": <integer rupee amount>,
  "timeline": "immediate|this_week|this_month|before_<date>",
  "reasoning": "why this specific instrument and amount",
  "expected_outcome": "what this achieves for the portfolio",
  "tax_note": "any STCG/LTCG implications"
}}

Rules:
- Be SPECIFIC. Name the exact fund or stock. Never say "an equity fund".
- Amount must be a specific number, not a range.
- Reasoning must reference the user's actual portfolio data above.
- If no action is needed, use action="hold" with reasoning."""

    try:
        proposal = await RECOMMENDATION.generate_json(prompt)
    except Exception as e:
        proposal = {
            "action": "hold",
            "instrument": "current portfolio",
            "amount_inr": 0,
            "timeline": "this_month",
            "reasoning": f"Unable to generate specific recommendation: {str(e)[:50]}",
            "expected_outcome": "Maintain current allocation",
            "tax_note": "No tax implications",
        }

    state["proposal"] = proposal
    state["reasoning_trace"] = state.get("reasoning_trace", []) + [
        f"Recommendation: {proposal.get('action', 'hold').upper()} {proposal.get('instrument', '')} "
        f"₹{proposal.get('amount_inr', 0):,} — {proposal.get('timeline', '')}"
    ]
    return state
