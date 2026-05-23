"""
THE ONLY FILE YOU TOUCH TO SWAP MODELS.

Assigns a provider instance to each agent role.
To swap Orchestrator to Claude: change one line below.

Environment-aware:
  ENVIRONMENT=production  → VertexAIProvider (GCP service account, no API key on Cloud Run)
  anything else           → GeminiProvider (AI Studio API key, free for local dev)
"""

from config import settings
from llm.base import BaseLLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.vertex import VertexAIProvider
from llm.providers.anthropic import AnthropicProvider


def _auto(model: str, temperature: float = 0.3) -> BaseLLMProvider:
    """Returns VertexAIProvider in production, GeminiProvider otherwise."""
    if settings.environment == "production":
        return VertexAIProvider(model=model, temperature=temperature)
    return GeminiProvider(model=model, temperature=temperature)


# ============================================================
# AGENT MODEL ASSIGNMENTS — change any line here to swap a model
# ============================================================

# User-facing agents — Pro for best reasoning quality
ORCHESTRATOR:        BaseLLMProvider = _auto("gemini-1.5-pro",   temperature=0.3)
RECOMMENDATION:      BaseLLMProvider = _auto("gemini-1.5-pro",   temperature=0.3)
MARKET_INTELLIGENCE: BaseLLMProvider = _auto("gemini-1.5-pro",   temperature=0.2)

# Background agents — Flash for speed and cost
DEVIL_ADVOCATE:      BaseLLMProvider = _auto("gemini-1.5-flash", temperature=0.2)
PROACTIVE_ALERT:     BaseLLMProvider = _auto("gemini-1.5-flash", temperature=0.1)
NEWS_INTELLIGENCE:   BaseLLMProvider = _auto("gemini-1.5-flash", temperature=0.1)
GOAL_TRACKER:        BaseLLMProvider = _auto("gemini-1.5-flash", temperature=0.1)
CONCENTRATION_RISK:  BaseLLMProvider = _auto("gemini-1.5-flash", temperature=0.1)

# ============================================================
# EXAMPLE: Swap Orchestrator to Claude (one-line change):
# ORCHESTRATOR = AnthropicProvider(model="claude-sonnet-4-20250514", temperature=0.3)
# ============================================================
