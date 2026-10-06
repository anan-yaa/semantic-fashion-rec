"""Query understanding service: orchestrates an LLMProvider call with a
mandatory fallback, a hard catalogue-vocabulary validation gate, and
filter-merge precedence rules. The route never talks to an LLMProvider
directly - it only ever calls understand_query() below.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.providers.llm_base import (
    LLMProvider,
    LLMProviderError,
    LLMRateLimitedError,
    LLMUnavailableError,
    UnsupportedQueryError,
)
from app.schemas.search import SearchFilter
from app.services.query_understanding.circuit_breaker import llm_circuit_breaker

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
    # Safe to show users, unlike `error`: FALLBACK_UNSUPPORTED_QUERY or FALLBACK_LLM_UNAVAILABLE.
    fallback_reason: Optional[str] = None
    # cleaned_query is an English translation of a non-English query
    translated: bool = False


FALLBACK_UNSUPPORTED_QUERY = "unsupported_query"
FALLBACK_LLM_UNAVAILABLE = "llm_unavailable"


def validate_filters(
    raw: SearchFilter, valid_values: Dict[str, List[str]]
) -> SearchFilter:
    """Drop any filter value that is not an exact member of the live catalogue
    vocabulary. This is a plain equality check against real catalogue values,
    independent of whatever the LLM provider returned or why - it is the hard
    guarantee that a hallucinated, malformed, or otherwise invalid value can
    never reach search_hybrid()'s filters, regardless of how it got here.
    """
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


def understand_query(
    provider: LLMProvider, query: str, valid_filters: Dict[str, List[str]]
) -> QueryUnderstandingResult:
    """Run query understanding with a mandatory, non-raising fallback.

    `valid_filters` is the live catalogue vocabulary (see
    vocabulary.get_catalogue_facets); the LLM may only return values from it.

    Returns ONLY LLM-inferred filters (unmerged with user filters). The caller
    is responsible for merging user-supplied filters with these LLM-inferred
    ones, and deciding which filters apply to which search paths (e.g. LLM
    filters only apply to keyword search, not vector).

    On any LLMProviderError, falls back to exactly today's behavior: the
    original query text, unchanged, with no inferred filters. This function
    never raises - a failure here must never turn into a 500 on /search.

    Circuit breaker: after repeated timeouts/connection errors (or one rate
    limit) the LLM is skipped instantly for a cooldown, instead of every
    search waiting for the LLM timeout. See circuit_breaker.py.
    """
    if not llm_circuit_breaker.allow_request():
        return _fallback(query, "LLM circuit breaker open", FALLBACK_LLM_UNAVAILABLE)

    try:
        result = provider.understand_query(query, valid_filters)
    except UnsupportedQueryError as e:
        llm_circuit_breaker.release()
        logger.info(f"Query understanding skipped: {e}")
        return _fallback(query, str(e), FALLBACK_UNSUPPORTED_QUERY)
    except LLMUnavailableError as e:
        llm_circuit_breaker.record_failure(immediate=isinstance(e, LLMRateLimitedError))
        logger.warning(f"LLM unavailable, falling back to raw query: {e}")
        return _fallback(query, str(e), FALLBACK_LLM_UNAVAILABLE)
    except LLMProviderError as e:
        # The service answered, just unusably (e.g. invalid JSON): not an outage.
        llm_circuit_breaker.record_success()
        logger.warning(f"Query understanding failed, falling back to raw query: {e}")
        return _fallback(query, str(e), FALLBACK_LLM_UNAVAILABLE)
    except BaseException:
        llm_circuit_breaker.release()
        raise

    llm_circuit_breaker.record_success()
    return QueryUnderstandingResult(
        cleaned_query=result.cleaned_query or query,
        filters=validate_filters(result.filters, valid_filters),  # LLM-inferred only
        used_llm=True,
        translated=result.translated and bool(result.cleaned_query),
    )


def search_texts(query: str, understanding: Optional[QueryUnderstandingResult]) -> Tuple[str, str]:
    """(vector search text, keyword search text) for a query.

    A non-English query the LLM translated is searched in English on both
    paths: the catalogue is English, and the multilingual embedding model alone
    matches some languages by spelling rather than meaning ("chaqueta" ->
    "Red Chief" shoes). English queries are searched with the user's own words:
    measured LLM rewrites of English queries dropped useful words
    ("durable sandals for everyday wear" -> "durable sandals") and lowered
    quality, so for them the LLM only contributes filters.
    """
    if understanding is not None and understanding.used_llm and understanding.translated:
        return understanding.cleaned_query, understanding.cleaned_query
    return query, query


def _fallback(query: str, error: str, reason: str) -> QueryUnderstandingResult:
    """The original query, no inferred filters: plain search."""
    return QueryUnderstandingResult(
        cleaned_query=query,
        filters=SearchFilter(),
        used_llm=False,
        error=error,
        fallback_reason=reason,
    )
