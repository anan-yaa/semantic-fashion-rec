"""Builds labeling pools by running all 3 search methods per query.

The pool for a query is the union of candidates returned by VECTOR,
KEYWORD, and HYBRID search (deduplicated by product id). HYBRID is run
explicitly, not just derived from the other two, because RRF fusion order
can surface an item inside hybrid's own top-k that wasn't near the top of
either raw list alone.
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.providers.base import EmbeddingProvider
from app.schemas.search import SearchMethod
from app.services.eval.io import PoolCandidate, PoolEntry, QuerySetEntry, save_pool
from app.services.search import search_hybrid

logger = logging.getLogger(__name__)

_METHODS = [SearchMethod.VECTOR, SearchMethod.KEYWORD, SearchMethod.HYBRID]


@dataclass
class PoolBuildStats:
    query_count: int
    total_candidates: int
    total_time_ms: float


def build_pool(
    session: Session,
    provider: EmbeddingProvider,
    queries: list[QuerySetEntry],
    k_per_method: int = 20,
) -> tuple[list[PoolEntry], PoolBuildStats]:
    start = time.time()
    pools: list[PoolEntry] = []
    total_candidates = 0

    for q in queries:
        candidates_by_id = {}

        for method in _METHODS:
            try:
                results, _, _ = search_hybrid(
                    session, q.query, provider, method=method, limit=k_per_method
                )
            except Exception as e:
                logger.warning(f"{method.value} search failed for query {q.id!r}: {e}")
                results = []

            for product in results:
                if product.id not in candidates_by_id:
                    candidates_by_id[product.id] = PoolCandidate(
                        product_id=product.id,
                        external_product_id=product.external_product_id,
                        name=product.name,
                        category=product.category,
                        subcategory=product.subcategory,
                        gender=product.gender,
                        color=product.color,
                        season=product.season,
                        search_text=product.search_text,
                        found_by=[method.value],
                    )
                else:
                    candidates_by_id[product.id].found_by.append(method.value)

        candidates = list(candidates_by_id.values())
        total_candidates += len(candidates)
        pools.append(PoolEntry(query_id=q.id, query=q.query, candidates=candidates))
        logger.info(f"Pooled {len(candidates)} candidates for query {q.id!r} ({q.query!r})")

    elapsed_ms = (time.time() - start) * 1000
    return pools, PoolBuildStats(
        query_count=len(queries), total_candidates=total_candidates, total_time_ms=elapsed_ms
    )


def build_and_save_pool(
    session: Session,
    provider: EmbeddingProvider,
    queries: list[QuerySetEntry],
    output_path: str,
    source_query_set: str,
    k_per_method: int = 20,
) -> PoolBuildStats:
    pools, stats = build_pool(session, provider, queries, k_per_method=k_per_method)
    save_pool(
        output_path,
        pools,
        source_query_set=source_query_set,
        k_per_method=k_per_method,
        built_at=datetime.now(timezone.utc).isoformat(),
    )
    return stats
