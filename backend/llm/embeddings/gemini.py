"""
Google text-embedding-004 via AI Studio API key, using the unified
google-genai SDK — same client pattern as llm/providers/gemini.py.
"""

from google import genai

from llm.embeddings.base import BaseEmbeddingProvider
from llm.retry import with_retry
from config import settings


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Connects to Google's text-embedding-004 via the AI Studio API key.
    """

    def __init__(self, model: str = "text-embedding-004"):
        self.model_name = model
        self.provider_name = "gemini"
        self.dimensions = 768
        self._client = genai.Client(api_key=settings.google_ai_api_key)

    async def embed(self, text: str) -> list[float]:
        response = await with_retry(lambda: self._client.aio.models.embed_content(
            model=self.model_name,
            contents=text,
        ))
        return response.embeddings[0].values
