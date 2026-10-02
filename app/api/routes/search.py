"""Search API route."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.providers.factory import get_embedding_provider
from app.schemas.search import SearchRequest, SearchResponse, SearchMethod
from app.services.search import search_hybrid
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    session: Session = Depends(get_session),
) -> SearchResponse:
    """Search the product catalogue.

    Supports hybrid search (combining vector + keyword), or individual methods.

    Args:
        request: SearchRequest with query and optional filters.
        session: Database session.

    Returns:
        SearchResponse with ranked products.
    """
    try:
        # Get embedding provider
        provider = get_embedding_provider(settings, use_fake=False)

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
