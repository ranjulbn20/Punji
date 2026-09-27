"""
Groq provider — free tier, used as a fallback when the primary provider is
unavailable (rate-limited, overloaded, or erroring). Not swapped in directly
via registry.py; wrap it with FallbackLLMProvider instead.
Requires GROQ_API_KEY in .env (free at console.groq.com).
"""
import json
import re
from groq import AsyncGroq
from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class GroqProvider(BaseLLMProvider):
    """Connects to Groq's free-tier Llama models via the official async client."""

    def __init__(self, model: str = "openai/gpt-oss-120b", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "groq"
        self._temperature = temperature
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    async def generate(self, prompt: str, temperature: float = None, use_search: bool = False) -> LLMResponse:
        # use_search is not implemented for this provider — ignored rather than raising.
        t = temperature if temperature is not None else self._temperature
        response = await self._client.chat.completions.create(
            model=self.model_name,
            temperature=t,
            messages=[{"role": "user", "content": prompt}],
        )
        msg = response.choices[0].message
        return LLMResponse(
            content=msg.content or "",
            model=self.model_name,
            provider=self.provider_name,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
        )

    async def generate_json(self, prompt: str, temperature: float = 0.1, use_search: bool = False) -> dict:
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Return only valid JSON. No explanation, no markdown, no code fences.\n"
            "Start your response with { and end with }."
        )
        response = await self._client.chat.completions.create(
            model=self.model_name,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": json_prompt}],
        )
        raw = response.choices[0].message.content or "{}"
        return _parse_json(raw)

    def as_langchain_llm(self):
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=self.model_name,
            groq_api_key=settings.groq_api_key,
            temperature=self._temperature,
        )


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq returned invalid JSON: {e}\nRaw response: {text[:500]}")
