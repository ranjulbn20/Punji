"""
Google Vertex AI provider, using the unified google-genai SDK.
Used in production on Cloud Run — authenticates via service account automatically.
For local development: run 'gcloud auth application-default login' first.
"""

import json
import re
from google import genai
from google.genai import types
from langchain_google_vertexai import ChatVertexAI

from llm.base import BaseLLMProvider, LLMResponse
from config import settings


class VertexAIProvider(BaseLLMProvider):
    """
    Connects to Gemini via Vertex AI.
    Authenticates automatically on Cloud Run; uses ADC for local dev.
    """

    def __init__(self, model: str = "gemini-flash-latest", temperature: float = 0.3):
        self.model_name = model
        self.provider_name = "vertex_ai"
        self._temperature = temperature
        self._client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gcp_region,
        )

    async def generate(self, prompt: str, temperature: float = None, use_search: bool = False) -> LLMResponse:
        t = temperature if temperature is not None else self._temperature
        config = types.GenerateContentConfig(
            temperature=t,
            tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None,
        )
        response = await self._client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
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
