"""
Fallback LLM provider — wraps a primary provider and retries against a
fallback provider if the primary raises. Composable over any BaseLLMProvider,
so it works the same whether the primary is Gemini or anything else added
later.
"""
import logging

from llm.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class FallbackLLMProvider(BaseLLMProvider):
    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
        self._primary = primary
        self._fallback = fallback
        self.provider_name = primary.provider_name
        self.model_name = primary.model_name

    async def generate(self, prompt: str, temperature: float = None, use_search: bool = False) -> LLMResponse:
        try:
            return await self._primary.generate(prompt, temperature=temperature, use_search=use_search)
        except Exception:
            logger.warning(
                "Primary provider %s failed, falling back to %s",
                self._primary.provider_name, self._fallback.provider_name, exc_info=True,
            )
            return await self._fallback.generate(prompt, temperature=temperature)

    async def generate_json(self, prompt: str, temperature: float = 0.1, use_search: bool = False) -> dict:
        try:
            return await self._primary.generate_json(prompt, temperature=temperature, use_search=use_search)
        except Exception:
            logger.warning(
                "Primary provider %s failed, falling back to %s",
                self._primary.provider_name, self._fallback.provider_name, exc_info=True,
            )
            return await self._fallback.generate_json(prompt, temperature=temperature)

    def as_langchain_llm(self):
        return self._primary.as_langchain_llm()
