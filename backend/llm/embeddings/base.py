"""
Abstract base class for all embedding providers.
Agents never call an embedding SDK directly — only this interface,
via the EMBEDDING instance assigned in llm/registry.py.
"""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """
    Abstract interface that all embedding providers implement.
    """

    provider_name: str
    model_name: str
    dimensions: int

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Returns a dense vector representation of text."""
        pass

    def __repr__(self):
        return f"{self.provider_name}({self.model_name})"
