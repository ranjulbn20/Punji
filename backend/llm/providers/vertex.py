"""
Google Vertex AI provider.
Used in production on Cloud Run — authenticates via service account automatically.
For local development: run 'gcloud auth application-default login' first.
"""

import asyncio
import json
import re
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from langchain_google_vertexai import ChatVertexAI

from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class VertexAIProvider(BaseLLMProvider):
    """
    Connects to Gemini via Vertex AI.
    Authenticates automatically on Cloud Run; uses ADC for local dev.
    """

    def __init__(self, model: str = "gemini-1.5-pro", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "vertex_ai"
        self._temperature = temperature

        vertexai.init(
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )
        self._client = GenerativeModel(
            model_name=model,
            generation_config=GenerationConfig(temperature=temperature),
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
        return ChatVertexAI(
            model_name=self.model_name,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
            temperature=self._temperature,
        )


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response: {text[:500]}")
