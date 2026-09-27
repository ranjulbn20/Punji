"""
THE ONLY FILE YOU TOUCH TO SWAP MODELS.

Assigns a provider instance to each agent role, plus the shared embedding
provider used for agent memory search.
"""

from config import settings
from llm.base import BaseLLMProvider
from llm.embeddings.base import BaseEmbeddingProvider
from llm.embeddings.gemini import GeminiEmbeddingProvider
from llm.fallback import FallbackLLMProvider
from llm.providers.gemini import GeminiProvider
from llm.providers.anthropic import AnthropicProvider
from llm.providers.groq_provider import GroqProvider


def _auto(model: str, temperature: float = 0.3) -> BaseLLMProvider:
    """
    Returns GeminiProvider (AI Studio API key), wrapped with a free-tier Groq
    fallback (llama-3.3-70b-versatile) whenever GROQ_API_KEY is set, so a
    Gemini outage/rate-limit doesn't take an agent down entirely. Without a
    key, the Gemini provider is returned as-is.
    """
    primary = GeminiProvider(model=model, temperature=temperature)
    if not settings.groq_api_key:
        return primary
    return FallbackLLMProvider(primary, GroqProvider(temperature=temperature))


# ============================================================
# AGENT MODEL ASSIGNMENTS — change any line here to swap a model
# ============================================================

# User-facing agents — flash-latest always tracks Google's newest Flash release
ORCHESTRATOR:        BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.3)
RECOMMENDATION:      BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.3)
MARKET_INTELLIGENCE: BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.2)

# Background agents — flash-latest (gemini-1.5-flash was retired by Google — 404s as of Sept 2026)
DEVIL_ADVOCATE:      BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.2)
PROACTIVE_ALERT:     BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.1)
NEWS_INTELLIGENCE:   BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.1)
GOAL_TRACKER:        BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.1)
CONCENTRATION_RISK:  BaseLLMProvider = _auto("gemini-flash-latest", temperature=0.1)

# Embeddings — used for agent memory semantic search (see agents/memory.py)
EMBEDDING: BaseEmbeddingProvider = GeminiEmbeddingProvider()

# ============================================================
# EXAMPLE: Swap Orchestrator to Claude (one-line change):
# ORCHESTRATOR = AnthropicProvider(model="claude-sonnet-4-20250514", temperature=0.3)
# ============================================================
