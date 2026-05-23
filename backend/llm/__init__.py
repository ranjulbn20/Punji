"""
Public interface for the LLM layer.
Agents import from here — never from providers directly.
"""

from llm.registry import (
    ORCHESTRATOR,
    RECOMMENDATION,
    MARKET_INTELLIGENCE,
    DEVIL_ADVOCATE,
    PROACTIVE_ALERT,
    NEWS_INTELLIGENCE,
    GOAL_TRACKER,
    CONCENTRATION_RISK,
)
from llm.base import LLMResponse, BaseLLMProvider

__all__ = [
    "ORCHESTRATOR",
    "RECOMMENDATION",
    "MARKET_INTELLIGENCE",
    "DEVIL_ADVOCATE",
    "PROACTIVE_ALERT",
    "NEWS_INTELLIGENCE",
    "GOAL_TRACKER",
    "CONCENTRATION_RISK",
    "LLMResponse",
    "BaseLLMProvider",
]
