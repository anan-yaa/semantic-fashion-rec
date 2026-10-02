"""Hybrid search combining vector and keyword methods via Reciprocal Rank Fusion."""
import logging
import time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.base import EmbeddingProvider
from app.schemas.search import SearchFilter, SearchMethod
from app.services.search.vector_search import search_vector
from app.services.search.keyword_search import search_keyword
from app.services.search.rank_fusion import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


def search_hybrid(
    session: Session,
    query_text: str,
    provider: EmbeddingProvider,
    filters: Optional[SearchFilter] = None,
    method: SearchMethod = SearchMethod.HYBRID,
    limit: int = 50,
) -> tuple[List[Product], SearchMethod, float]:
    """Unified search orchestration using Reciprocal Rank Fusion.

    Args:
        session: Database session.
        query_text: Search query.
        provider: EmbeddingProvider for vector search.
        filters: Optional search filters.
        method: Search method (HYBRID, VECTOR, or KEYWORD).
        limit: Maximum results to return.

    Returns:
        Tuple of (products, actual_method_used, time_ms).
    """
    start_time = time.time()

    try:
        if method == SearchMethod.VECTOR:
            # Vector search only
            products, _ = search_vector(
                session, query_text, provider, filters=filters, limit=limit
            )
            results = products[:limit]
            actual_method = SearchMethod.VECTOR

        elif method == SearchMethod.KEYWORD:
            # Keyword search only
            products, _ = search_keyword(
                session, query_text, filters=filters, limit=limit
            )
            results = products[:limit]
            actual_method = SearchMethod.KEYWORD

        else:  # HYBRID
            # Run both methods and fuse via Reciprocal Rank Fusion
            try:
                vector_results, _ = search_vector(
                    session, query_text, provider, filters=filters, limit=limit * 2
                )
            except Exception as e:
                logger.debug(f"Vector search failed: {e}")
                vector_results = []

            try:
                keyword_results, _ = search_keyword(
                    session, query_text, filters=filters, limit=limit * 2
                )
            except Exception as e:
                logger.debug(f"Keyword search failed: {e}")
                keyword_results = []

            # Fuse results using Reciprocal Rank Fusion
            results = reciprocal_rank_fusion(vector_results, keyword_results, k=60)
            results = results[:limit]
            actual_method = SearchMethod.HYBRID

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Search completed: {len(results)} results in {elapsed_ms:.1f}ms using {actual_method}")

        return results, actual_method, elapsed_ms

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        elapsed_ms = (time.time() - start_time) * 1000
        return [], method, elapsed_ms
