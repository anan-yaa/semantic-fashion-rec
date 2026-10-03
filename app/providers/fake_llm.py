"""Deterministic fake LLM provider for testing. Never calls a real API."""
from typing import Dict, List, Optional

from app.providers.llm_base import LLMProvider, LLMProviderError, QueryUnderstanding
from app.schemas.search import SearchFilter


class FakeLLMProvider(LLMProvider):
    """Deterministic query-understanding provider for tests.

    By default, returns the query unchanged with no inferred filters. Pass
    `canned_responses` to control the output for specific queries, or
    `raise_error=True` to exercise the fallback path in callers.
    """

    def __init__(
        self,
        canned_responses: Optional[Dict[str, QueryUnderstanding]] = None,
        raise_error: bool = False,
    ):
        self.canned_responses = canned_responses or {}
        self.raise_error = raise_error
        self.calls: List[str] = []

    def understand_query(
        self, query: str, valid_filters: Dict[str, List[str]]
    ) -> QueryUnderstanding:
        self.calls.append(query)

        if self.raise_error:
            raise LLMProviderError("FakeLLMProvider configured to raise")

        if query in self.canned_responses:
            return self.canned_responses[query]

        return QueryUnderstanding(cleaned_query=query, filters=SearchFilter())
