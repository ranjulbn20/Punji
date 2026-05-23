"""
Google Gemini provider via AI Studio API key.
Used for local development — free tier at aistudio.google.com.
"""

import asyncio
import json
import re
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class GeminiProvider(BaseLLMProvider):
    """
    Connects to Google Gemini via the AI Studio API key.
    Free for local development. Rate limits apply on free tier.
    """

    def __init__(self, model: str = "gemini-1.5-pro", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "gemini"
        self._temperature = temperature

        genai.configure(api_key=settings.google_ai_api_key)
        self._client = genai.GenerativeModel(
            model_name=model,
            generation_config=genai.GenerationConfig(temperature=temperature),
        )

    async def generate(self, prompt: str, temperature: float = None) -> LLMResponse:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.generate_content(prompt),
        )
        return LLMResponse(
            content=response.text,
            model=self.model_name,
            provider=self.provider_name,
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
