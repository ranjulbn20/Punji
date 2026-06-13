"""
OpenAI provider.
Swap any agent to GPT by setting its registry entry to OpenAIProvider(...).
Requires OPENAI_API_KEY in .env.
"""
import json
import re
from openai import AsyncOpenAI
from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class OpenAIProvider(BaseLLMProvider):
    """Connects to OpenAI via the official async client."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "openai"
        self._temperature = temperature
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(self, prompt: str, temperature: float = None) -> LLMResponse:
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

    async def generate_json(self, prompt: str, temperature: float = 0.1) -> dict:
        response = await self._client.chat.completions.create(
            model=self.model_name,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"OpenAI returned invalid JSON: {e}\nRaw: {raw[:500]}")

    def as_langchain_llm(self):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model_name,
            openai_api_key=settings.openai_api_key,
            temperature=self._temperature,
        )
