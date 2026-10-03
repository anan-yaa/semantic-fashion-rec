"""Abstract LLM provider interface for query understanding."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.schemas.search import SearchFilter


@dataclass
class QueryUnderstanding:
    """Raw output of an LLMProvider's query-understanding call."""

    cleaned_query: str
    filters: SearchFilter = field(default_factory=SearchFilter)
    reasoning: Optional[str] = None


class LLMProviderError(Exception):
    """Raised on any failure: network, timeout, or a malformed/unusable response.

    Providers must never swallow failures themselves - the caller (see
    app/services/query_understanding/service.py) owns the fallback decision,
    mirroring how EmbeddingProvider failures are handled one layer up in
    search_hybrid() rather than inside the provider.
    """


class LLMProvider(ABC):
    """Abstract base class for LLM query-understanding providers."""

    @abstractmethod
    def understand_query(
        self, query: str, valid_filters: Dict[str, List[str]]
    ) -> QueryUnderstanding:
        """Extract a cleaned keyword phrase and structured filters from a query.

        Args:
            query: The raw user search query.
            valid_filters: Maps each filter field name (category/gender/color/
                season) to the list of catalogue values currently allowed for
                it. Implementations must only return values present in these
                lists, or None.

        Returns:
            A QueryUnderstanding with the cleaned query and inferred filters.

        Raises:
            LLMProviderError: On any failure. Implementations must not return
                a silently degraded value themselves.
        """
