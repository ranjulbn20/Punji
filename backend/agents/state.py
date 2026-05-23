from typing import TypedDict, Optional


class PunjiState(TypedDict, total=False):
    # Input
    user_id: str
    user_query: str
    run_type: str  # 'conversational' | 'scheduled_daily' | 'scheduled_weekly'
    conversation_id: Optional[str]

    # User context (loaded at run start)
    risk_profile: Optional[dict]
    active_goals: list[dict]
    agent_memories: list[dict]

    # Intermediate outputs
    intent: Optional[str]
    allocation_report: Optional[dict]
    concentration_report: Optional[dict]
    market_context: Optional[dict]
    goal_analysis: Optional[dict]
    news_alerts: list[dict]
    proposal: Optional[dict]
    critique: Optional[dict]

    # Final outputs
    final_response: Optional[str]
    reasoning_trace: list[str]
    new_memories: list[dict]
    alerts_to_create: list[dict]

    # Control
    errors: list[str]
    current_agent: str
