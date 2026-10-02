"""Abstract embedding provider interface."""
from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimension."""
        pass

    @abstractmethod
    def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed passages for indexing.

        Args:
            texts: List of text passages to embed.

        Returns:
            List of embeddings, each a list of floats.
        """
        pass

    @abstractmethod
    def embed_queries(self, texts: List[str]) -> List[List[float]]:
        """Embed queries for search.

        Args:
            texts: List of search queries to embed.

        Returns:
            List of embeddings, each a list of floats.
        """
        pass
