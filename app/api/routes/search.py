"""Search API route."""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider
from app.providers.llm_base import LLMProvider
from app.providers.llm_factory import get_llm_provider
from app.schemas.search import SearchFilter, SearchRequest, SearchResponse, SearchMethod
from app.services.query_understanding import get_catalogue_facets, merge_filters, understand_query
from app.services.search import search_hybrid
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])

# Process-wide embedding provider singleton. The provider object itself is
# cheap to construct (it only records config and detects cuda/cpu); the
# actual model weights are loaded lazily inside the provider on first use
# (see HuggingFaceE5Provider._load_model). Caching the provider instance
# here - instead of constructing a new one per request - is what makes that
# lazy load happen once per process instead of once per request.
_provider: Optional[EmbeddingProvider] = None

# Process-wide LLM provider singleton, same rationale: avoid constructing a
# new genai.Client on every request.
_llm_provider: Optional[LLMProvider] = None


def get_search_provider() -> EmbeddingProvider:
    """FastAPI dependency returning a single shared embedding provider.

    Not called at application startup - only the first request that
    resolves this dependency constructs the provider, and every request
    after that (including the one that triggers the actual model load)
    reuses the same instance.
    """
    global _provider
    if _provider is None:
        _provider = get_embedding_provider(settings, use_fake=False)
    return _provider


def _reset_search_provider_cache() -> None:
    """Test-only hook to clear the cached singleton between test cases."""
    global _provider
    _provider = None


def get_query_understanding_provider() -> LLMProvider:
    """FastAPI dependency returning a single shared LLM provider."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = get_llm_provider(settings, use_fake=False)
    return _llm_provider


def _reset_query_understanding_provider_cache() -> None:
    """Test-only hook to clear the cached singleton between test cases."""
    global _llm_provider
    _llm_provider = None


@router.post("", response_model=SearchResponse)
def search(
    request: SearchRequest,
    session: Session = Depends(get_session),
    provider: EmbeddingProvider = Depends(get_search_provider),
    llm_provider: LLMProvider = Depends(get_query_understanding_provider),
) -> SearchResponse:
    """Search the product catalogue.

    Supports hybrid search (combining vector + keyword), or individual methods.
    When query_understanding_enabled, every query is first passed through an
    LLM to (a) infer structured filters from free text and (b) produce a
    keyword-dense rephrasing used only for the keyword-search path - vector
    search always uses the original query text. See
    app/services/query_understanding/service.py for the fallback and
    validation behavior if this fails or infers an out-of-vocabulary value.

    Args:
        request: SearchRequest with query and optional filters.
        session: Database session.
        provider: Shared embedding provider (see get_search_provider).
        llm_provider: Shared LLM provider (see get_query_understanding_provider).

    Returns:
        SearchResponse with ranked products.
    """
    try:
        keyword_query_text = None
        user_filters = request.filters or SearchFilter()
        if user_filters.availability is None:
            # Products dropped from the catalogue feed stay in the DB as
            # unavailable; hide them unless the caller asks otherwise.
            user_filters = user_filters.model_copy(update={"availability": True})
        vector_filters = user_filters
        keyword_filters = user_filters
        llm_latency_ms = 0.0
        used_llm = False
        llm_error = None

        if settings.query_understanding_enabled:
            llm_start = time.time()
            understanding = understand_query(
                llm_provider, request.query, get_catalogue_facets(session)
            )
            llm_latency_ms = (time.time() - llm_start) * 1000

            keyword_query_text = understanding.cleaned_query
            used_llm = understanding.used_llm
            llm_error = understanding.error

            # LLM-inferred filters apply to keyword search only.
            # User-supplied filters always win over LLM inferences.
            keyword_filters = merge_filters(user_filters, understanding.filters)

        # Execute search
        products, method_used, search_time_ms = search_hybrid(
            session,
            query_text=request.query,
            provider=provider,
            filters=vector_filters,  # User filters only - LLM filters never constrain vector search
            method=request.method,
            limit=request.limit,
            keyword_query_text=keyword_query_text,
            keyword_filters=keyword_filters,  # User + LLM-inferred filters for keyword path
        )

        # Structured logging for observability
        logger.info(
            f"search_complete",
            extra={
                "query": request.query[:100],  # Truncate for logging
                "method": method_used.value,
                "results": len(products),
                "search_ms": search_time_ms,
                "llm_used": used_llm,
                "llm_latency_ms": llm_latency_ms,
                "llm_error": llm_error,
            }
        )

        # Build response
        return SearchResponse(
            products=[p for p in products],  # Schema will convert via from_attributes
            query=request.query,
            method=method_used,
            total_products=len(products),
            took_ms=search_time_ms + llm_latency_ms,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")
