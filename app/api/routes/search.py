"""Search API route."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider
from app.schemas.search import SearchRequest, SearchResponse, SearchMethod
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


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    session: Session = Depends(get_session),
    provider: EmbeddingProvider = Depends(get_search_provider),
) -> SearchResponse:
    """Search the product catalogue.

    Supports hybrid search (combining vector + keyword), or individual methods.

    Args:
        request: SearchRequest with query and optional filters.
        session: Database session.
        provider: Shared embedding provider (see get_search_provider).

    Returns:
        SearchResponse with ranked products.
    """
    try:
        # Execute search
        products, method_used, time_ms = search_hybrid(
            session,
            query_text=request.query,
            provider=provider,
            filters=request.filters,
            method=request.method,
            limit=request.limit,
        )

        # Build response
        return SearchResponse(
            products=[p for p in products],  # Schema will convert via from_attributes
            query=request.query,
            method=method_used,
            total_products=len(products),
            took_ms=time_ms,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")
