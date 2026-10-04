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
    keyword_query_text: Optional[str] = None,
    keyword_filters: Optional[SearchFilter] = None,
) -> tuple[List[Product], SearchMethod, float]:
    """Unified search orchestration using Reciprocal Rank Fusion.

    Args:
        session: Database session.
        query_text: Search query (used for vector search, and for keyword
            search when keyword_query_text is not supplied).
        provider: EmbeddingProvider for vector search.
        filters: Optional search filters (applied to vector search).
        method: Search method (HYBRID, VECTOR, or KEYWORD).
        limit: Maximum results to return.
        keyword_query_text: Optional alternate query text for the keyword
            path only (e.g. an LLM-cleaned, keyword-dense rephrasing).
            Defaults to query_text when not supplied - vector search always
            uses query_text regardless.
        keyword_filters: Optional search filters for the keyword path only.
            Defaults to `filters` when not supplied - for backward compatibility,
            both vector and keyword use the same filters. When supplied separately,
            allows LLM-inferred filters to apply only to keyword search.

    Returns:
        Tuple of (products, actual_method_used, time_ms).
    """
    start_time = time.time()
    kw_query_text = keyword_query_text if keyword_query_text is not None else query_text
    kw_filters = keyword_filters if keyword_filters is not None else filters

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
                session, kw_query_text, filters=kw_filters, limit=limit
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
                    session, kw_query_text, filters=kw_filters, limit=limit * 2
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
