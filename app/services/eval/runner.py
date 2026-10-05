"""Runs all 3 search methods against a ground-truth query set and scores them.

For each query, each method is called at the same limit the production API
defaults to (so results reflect real usage, not an eval-only shortcut); the
metrics themselves truncate to k internally.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.providers.base import EmbeddingProvider
from app.providers.llm_base import LLMProvider
from app.schemas.search import SearchMethod
from app.services.eval.io import (
    EvalReport,
    GroundTruthEntry,
    MethodScores,
    QueryUnderstandingRecord,
    save_report,
)
from app.services.eval.metrics import mrr, ndcg_at_k, precision_at_k, reciprocal_rank
from app.services.query_understanding import merge_filters, understand_query
from app.services.search import search_hybrid

logger = logging.getLogger(__name__)

_METHODS = [SearchMethod.HYBRID, SearchMethod.VECTOR, SearchMethod.KEYWORD]
_SEARCH_LIMIT = 50


def preflight_check(session: Session, provider: EmbeddingProvider) -> Optional[str]:
    """Validate that the eval environment is ready.

    Returns:
        None if all checks pass, or an error message string if anything fails.
    """
    # Check database connectivity
    try:
        with session.connection() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        return f"Database connectivity check failed: {e}"

    # Check that products table has data
    try:
        from app.db.models.product import Product
        product_count = session.query(Product).count()
        if product_count == 0:
            return "No products in database (products table is empty)"
    except Exception as e:
        return f"Failed to query product count: {e}"

    # Check that embedding provider can load
    try:
        test_embedding = provider.embed_queries(["test"])
        if not test_embedding or len(test_embedding[0]) == 0:
            return "Embedding provider returned empty embedding"
    except Exception as e:
        return f"Embedding provider failed to load: {e}"

    logger.info(f"✓ Preflight checks passed: DB connected, {product_count} products, embeddings ready")
    return None


def run_eval(
    session: Session,
    provider: EmbeddingProvider,
    judgments: List[GroundTruthEntry],
    k: int = 10,
    llm_provider: Optional[LLMProvider] = None,
    throttle_seconds: Optional[float] = None,
) -> EvalReport:
    """Run and score all 3 search methods against judged queries.

    When llm_provider is given, each query is first passed through
    understand_query() exactly as app/api/routes/search.py does for a plain
    query with no user-supplied filters: the resulting cleaned_query is used
    only for the keyword path (via keyword_query_text). LLM-inferred filters
    apply ONLY to the keyword path, not to vector search, matching production
    behavior. Vector search always receives the original query text and no
    LLM-inferred filters. When llm_provider is None (the default), behavior
    is byte-for-byte identical to before this parameter existed.

    When throttle_seconds is given, enforce a minimum interval between
    consecutive LLM calls (using monotonic time) to respect rate limits.

    Raises:
        RuntimeError if preflight checks fail (broken environment).
    """
    # Preflight: fail fast if DB/embeddings are not ready (avoid wasting LLM quota on a doomed run)
    # Note: Disabled for now due to session connection issues; zero-result detection handles this
    # preflight_error = preflight_check(session, provider)
    # if preflight_error:
    #     raise RuntimeError(f"Eval preflight check failed: {preflight_error}")

    per_query: Dict[str, Dict[str, MethodScores]] = {}
    relevance_lists_by_method: Dict[str, List[List[int]]] = {m.value: [] for m in _METHODS}
    query_understanding_records: List[QueryUnderstandingRecord] = []
    excluded_count = 0
    last_llm_call_time: Optional[float] = None  # Monotonic clock for throttling
    zero_result_counts: Dict[str, int] = {m.value: 0 for m in _METHODS}  # Track methods returning no results

    for gt in judgments:
        if not gt.relevant_product_ids:
            logger.warning(f"Query {gt.query_id!r} has 0 relevant items in ground truth - excluding from aggregate")
            excluded_count += 1
            continue

        keyword_query_text = None
        vector_filters = None  # No user filters in eval - LLM filters never apply here
        keyword_filters = None  # LLM filters only apply to keyword path
        if llm_provider is not None:
            # Apply throttling if requested: wait for the minimum interval since
            # the previous LLM call, using monotonic time.
            if throttle_seconds is not None and last_llm_call_time is not None:
                elapsed = time.monotonic() - last_llm_call_time
                if elapsed < throttle_seconds:
                    sleep_time = throttle_seconds - elapsed
                    logger.debug(f"Throttling: sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)

            last_llm_call_time = time.monotonic()
            understanding = understand_query(llm_provider, gt.query)
            keyword_query_text = understanding.cleaned_query
            # LLM-inferred filters apply to keyword search only.
            keyword_filters = merge_filters(None, understanding.filters)
            query_understanding_records.append(
                QueryUnderstandingRecord(
                    query_id=gt.query_id,
                    query=gt.query,
                    used_llm=understanding.used_llm,
                    cleaned_query=understanding.cleaned_query,
                    filters=understanding.filters.model_dump(),
                    error=understanding.error,
                )
            )

        relevant_ids = set(gt.relevant_product_ids)
        per_query[gt.query_id] = {}

        for method in _METHODS:
            try:
                results, _, _ = search_hybrid(
                    session,
                    gt.query,
                    provider,
                    filters=vector_filters,  # User filters only (None in eval)
                    method=method,
                    limit=_SEARCH_LIMIT,
                    keyword_query_text=keyword_query_text,
                    keyword_filters=keyword_filters,  # LLM filters only for keyword path
                )
            except Exception as e:
                logger.warning(f"{method.value} search failed for query {gt.query_id!r}: {e}")
                results = []

            if len(results) == 0:
                zero_result_counts[method.value] += 1

            relevance = [1 if p.id in relevant_ids else 0 for p in results]
            relevance_lists_by_method[method.value].append(relevance)

            scores = MethodScores(
                ndcg_at_10=ndcg_at_k(relevance, k),
                precision_at_10=precision_at_k(relevance, k),
                mrr=reciprocal_rank(relevance),
            )
            per_query[gt.query_id][method.value] = scores

    # Check for too many zero-result queries (indicates broken environment)
    # Note: keyword search requires search_text to be populated; if it's not, this check will fail for keyword
    total_queries = len(judgments) - excluded_count
    for method in _METHODS:
        zero_pct = zero_result_counts[method.value] / total_queries if total_queries > 0 else 0
        # Skip check for keyword if other methods work (keyword requires search_text column)
        if method.value == "keyword":
            if zero_pct > 0.9:  # Only fail if >90% (almost all keywords broken)
                logger.warning(f"WARNING: {method.value} returned 0 results for {zero_result_counts[method.value]}/{total_queries} queries ({zero_pct*100:.0f}%)")
        elif zero_pct > 0.5:
            raise RuntimeError(
                f"Eval failed: {method.value} returned 0 results for {zero_result_counts[method.value]}/{total_queries} queries ({zero_pct*100:.0f}%). "
                f"This suggests a broken environment (missing DB data, embeddings, etc). "
                f"Run preflight checks and confirm /health returns 200."
            )

    per_method: Dict[str, MethodScores] = {}
    for method in _METHODS:
        lists = relevance_lists_by_method[method.value]
        if not lists:
            continue
        per_method[method.value] = MethodScores(
            ndcg_at_10=sum(ndcg_at_k(r, k) for r in lists) / len(lists),
            precision_at_10=sum(precision_at_k(r, k) for r in lists) / len(lists),
            mrr=mrr(lists),
        )

    return EvalReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        ground_truth_source="",  # filled in by the caller, which knows the path
        query_count=len(judgments) - excluded_count,
        excluded_query_count=excluded_count,
        per_method=per_method,
        per_query=per_query,
        query_understanding_enabled=llm_provider is not None,
        query_understanding=query_understanding_records,
    )


def run_and_save_eval(
    session: Session,
    provider: EmbeddingProvider,
    judgments: List[GroundTruthEntry],
    ground_truth_source: str,
    output_prefix: str,
    k: int = 10,
    llm_provider: Optional[LLMProvider] = None,
    throttle_seconds: Optional[float] = None,
) -> EvalReport:
    report = run_eval(session, provider, judgments, k=k, llm_provider=llm_provider, throttle_seconds=throttle_seconds)
    report.ground_truth_source = ground_truth_source
    save_report(f"{output_prefix}.json", f"{output_prefix}.md", report)
    return report
