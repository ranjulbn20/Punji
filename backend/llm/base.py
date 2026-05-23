"""
Abstract base class for all LLM providers.
Every provider (Gemini, Vertex AI, Claude) must implement this interface.
Agents never import provider SDKs directly — only this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardised response from any LLM provider."""
    content: str
    model: str
    provider: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class BaseLLMProvider(ABC):
    """
    Abstract interface that all LLM providers implement.
    Agents call generate() or generate_json() — never provider-specific methods.
    """

    provider_name: str
    model_name: str

    @abstractmethod
    async def generate(self, prompt: str, temperature: float = 0.3) -> LLMResponse:
        """Single-turn generation."""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, temperature: float = 0.1) -> dict:
        """
        Generate and parse JSON response.
        Prompt must instruct the model to return only valid JSON.
        """
        pass

    @abstractmethod
    def as_langchain_llm(self):
        """Returns a LangChain-compatible LLM object for LangGraph nodes."""
        pass

    def __repr__(self):
        return f"{self.provider_name}({self.model_name})"
