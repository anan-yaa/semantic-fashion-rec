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
from app.services.search.product_types import detect_article_types
from app.services.search.rank_fusion import reciprocal_rank_fusion

logger = logging.getLogger(__name__)

# Keyword hits fused into hybrid must match at least this fraction of the
# query's terms (rounded up): 2 of 2, 3 of 3, 3 of 4, 4 of 5. Products matching
# only some words of a multi-word query add noise rather than recall. Tuned on
# ground_truth_v2_real: NDCG@10 0.694 (no threshold) / 0.804 (0.6) / 0.825 (0.75)
# / 0.832 (1.0, i.e. AND).
KEYWORD_MIN_TERM_COVERAGE = 0.75
# Fallback when results are restricted to a product type and nothing meets the
# strict threshold.
RELAXED_KEYWORD_MIN_TERM_COVERAGE = 0.5


def _fused_search(
    session: Session,
    query_text: str,
    provider: EmbeddingProvider,
    filters: Optional[SearchFilter],
    kw_query_text: str,
    kw_filters: Optional[SearchFilter],
    limit: int,
    article_types: Optional[List[str]],
) -> List[Product]:
    """Run vector and keyword search and fuse them with Reciprocal Rank Fusion."""
    try:
        vector_results, _ = search_vector(
            session, query_text, provider, filters=filters, limit=limit * 2,
            article_types=article_types,
        )
    except Exception as e:
        logger.debug(f"Vector search failed: {e}")
        vector_results = []

    try:
        keyword_results, _ = search_keyword(
            session,
            kw_query_text,
            filters=kw_filters,
            limit=limit * 2,
            min_term_coverage=KEYWORD_MIN_TERM_COVERAGE,
            article_types=article_types,
        )
        if article_types and not keyword_results:
            # Nothing matches every term (no "black leather jacket" exists), but
            # within the named type a partial match ("black jacket") is still
            # relevant and carries the color/gender filters into the ranking.
            keyword_results, _ = search_keyword(
                session,
                kw_query_text,
                filters=kw_filters,
                limit=limit * 2,
                min_term_coverage=RELAXED_KEYWORD_MIN_TERM_COVERAGE,
                article_types=article_types,
            )
    except Exception as e:
        logger.debug(f"Keyword search failed: {e}")
        keyword_results = []

    return reciprocal_rank_fusion(vector_results, keyword_results, k=60)[:limit]


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
            try:
                article_types = detect_article_types(session, query_text)
            except Exception as e:
                logger.warning(f"Product type detection failed, searching all types: {e}")
                article_types = []

            results = _fused_search(
                session, query_text, provider, filters, kw_query_text, kw_filters, limit, article_types
            )
            if article_types and not results:
                # Nothing of the named type passes the other filters; better to
                # show related products than an empty page.
                results = _fused_search(
                    session, query_text, provider, filters, kw_query_text, kw_filters, limit, None
                )
            actual_method = SearchMethod.HYBRID

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Search completed: {len(results)} results in {elapsed_ms:.1f}ms using {actual_method}")

        return results, actual_method, elapsed_ms

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        elapsed_ms = (time.time() - start_time) * 1000
        return [], method, elapsed_ms
