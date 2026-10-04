"""Query understanding service: orchestrates an LLMProvider call with a
mandatory fallback, a hard catalogue-vocabulary validation gate, and
filter-merge precedence rules. The route never talks to an LLMProvider
directly - it only ever calls understand_query() below.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.providers.llm_base import LLMProvider, LLMProviderError
from app.schemas.search import SearchFilter
from app.services.query_understanding.vocabulary import CATALOGUE_FACETS

logger = logging.getLogger(__name__)

# SearchFilter fields an LLM could plausibly infer from free text. Excludes
# `availability`, which is never inferable from query text.
_INFERABLE_FIELDS = ("category", "gender", "color", "season")


@dataclass
class QueryUnderstandingResult:
    """Outcome of understand_query() - always safe for the caller to use."""

    cleaned_query: str
    filters: SearchFilter
    used_llm: bool
    error: Optional[str] = None


def validate_filters(
    raw: SearchFilter, valid_values: Optional[Dict[str, List[str]]] = None
) -> SearchFilter:
    """Drop any filter value that is not an exact member of the live catalogue
    vocabulary. This is a plain equality check against real catalogue values,
    independent of whatever the LLM provider returned or why - it is the hard
    guarantee that a hallucinated, malformed, or otherwise invalid value can
    never reach search_hybrid()'s filters, regardless of how it got here.
    """
    valid_values = valid_values if valid_values is not None else CATALOGUE_FACETS
    validated = SearchFilter()
    for field_name in _INFERABLE_FIELDS:
        value = getattr(raw, field_name)
        if value is not None and value in valid_values.get(field_name, []):
            setattr(validated, field_name, value)
        elif value is not None:
            logger.warning(
                f"Dropping out-of-vocabulary LLM-inferred filter: {field_name}={value!r}"
            )
    return validated


def merge_filters(user_filters: Optional[SearchFilter], llm_filters: SearchFilter) -> SearchFilter:
    """Merge user-supplied and LLM-inferred filters.

    An explicit user-supplied value always wins over an LLM-inferred one for
    the same field. `availability` is always sourced from the user only - the
    LLM never populates it.
    """
    user_filters = user_filters or SearchFilter()
    merged = SearchFilter(availability=user_filters.availability)
    for field_name in _INFERABLE_FIELDS:
        user_value = getattr(user_filters, field_name)
        setattr(merged, field_name, user_value if user_value is not None else getattr(llm_filters, field_name))
    return merged


def understand_query(provider: LLMProvider, query: str) -> QueryUnderstandingResult:
    """Run query understanding with a mandatory, non-raising fallback.

    Returns ONLY LLM-inferred filters (unmerged with user filters). The caller
    is responsible for merging user-supplied filters with these LLM-inferred
    ones, and deciding which filters apply to which search paths (e.g. LLM
    filters only apply to keyword search, not vector).

    On any LLMProviderError, falls back to exactly today's behavior: the
    original query text, unchanged, with no inferred filters. This function
    never raises - a failure here must never turn into a 500 on /search.
    """
    try:
        result = provider.understand_query(query, CATALOGUE_FACETS)
        validated = validate_filters(result.filters)
        return QueryUnderstandingResult(
            cleaned_query=result.cleaned_query or query,
            filters=validated,  # LLM-inferred only
            used_llm=True,
        )
    except LLMProviderError as e:
        logger.warning(f"Query understanding failed, falling back to raw query: {e}")
        return QueryUnderstandingResult(
            cleaned_query=query,
            filters=SearchFilter(),  # Empty - no LLM inference
            used_llm=False,
            error=str(e),
        )
