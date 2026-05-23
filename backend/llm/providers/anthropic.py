"""
Anthropic Claude provider.
Not used by default — swap in for any agent by changing its entry in registry.py.
Requires ANTHROPIC_API_KEY in .env.
"""

import json
import re
from anthropic import AsyncAnthropic
from langchain_anthropic import ChatAnthropic

from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class AnthropicProvider(BaseLLMProvider):
    """
    Connects to Claude via Anthropic API.
    Recommended for: Orchestrator, Recommendation Agent in production.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "anthropic"
        self._temperature = temperature
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(self, prompt: str, temperature: float = None) -> LLMResponse:
        t = temperature if temperature is not None else self._temperature
        message = await self._client.messages.create(
            model=self.model_name,
            max_tokens=2048,
            temperature=t,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            content=message.content[0].text,
            model=self.model_name,
            provider=self.provider_name,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )

    async def generate_json(self, prompt: str, temperature: float = 0.1) -> dict:
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Return only valid JSON. No explanation, no markdown, no code fences.\n"
            "Start your response with { and end with }."
        )
        response = await self.generate(json_prompt, temperature=temperature)
        return _parse_json(response.content)

    def as_langchain_llm(self):
        return ChatAnthropic(
            model=self.model_name,
            anthropic_api_key=settings.anthropic_api_key,
            temperature=self._temperature,
        )


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response: {text[:500]}")
