"""Abstract embedding provider interface."""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Embedding dimension."""

    @abstractmethod
    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing.

        Args:
            texts: List of text passages to embed.

        Returns:
            List of embeddings, each a list of floats.
        """

    def warm_up(self) -> None:
        """Load any model weights ahead of the first request. No-op by default."""

    @abstractmethod
    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed queries for search.

        Args:
            texts: List of search queries to embed.

        Returns:
            List of embeddings, each a list of floats.
        """
