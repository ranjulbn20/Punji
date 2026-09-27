"""
Google Gemini provider via AI Studio API key, using the unified google-genai SDK.
Used for local development — free tier at aistudio.google.com.
"""

import json
import re
from google import genai
from google.genai import types
from langchain_google_genai import ChatGoogleGenerativeAI

from llm.base import BaseLLMProvider, LLMResponse
from llm.retry import with_retry
from config import settings


class GeminiProvider(BaseLLMProvider):
    """
    Connects to Google Gemini via the AI Studio API key.
    Free for local development. Rate limits apply on free tier.
    """

    def __init__(self, model: str = "gemini-flash-latest", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "gemini"
        self._temperature = temperature
        self._client = genai.Client(api_key=settings.google_ai_api_key)

    async def generate(self, prompt: str, temperature: float = None, use_search: bool = False) -> LLMResponse:
        t = temperature if temperature is not None else self._temperature
        config = types.GenerateContentConfig(
            temperature=t,
            tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None,
        )
        response = await with_retry(lambda: self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        ))
        return LLMResponse(
            content=response.text,
            model=self.model_name,
            provider=self.provider_name,
        )

    async def generate_json(self, prompt: str, temperature: float = 0.1, use_search: bool = False) -> dict:
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Return only valid JSON. No explanation, no markdown, no code fences.\n"
            "Start your response with { and end with }."
        )
        response = await self.generate(json_prompt, temperature=temperature, use_search=use_search)
        return _parse_json(response.content)

    def as_langchain_llm(self):
        return ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=settings.google_ai_api_key,
            temperature=self._temperature,
            convert_system_message_to_human=True,
        )


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response: {text[:500]}")
