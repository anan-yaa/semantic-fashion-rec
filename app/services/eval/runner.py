"""Runs all 3 search methods against a ground-truth query set and scores them.

For each query, each method is called at the same limit the production API
defaults to (so results reflect real usage, not an eval-only shortcut); the
metrics themselves truncate to k internally.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.providers.base import EmbeddingProvider
from app.schemas.search import SearchMethod
from app.services.eval.io import EvalReport, GroundTruthEntry, MethodScores, save_report
from app.services.eval.metrics import mrr, ndcg_at_k, precision_at_k, reciprocal_rank
from app.services.search import search_hybrid

logger = logging.getLogger(__name__)

_METHODS = [SearchMethod.HYBRID, SearchMethod.VECTOR, SearchMethod.KEYWORD]
_SEARCH_LIMIT = 50


def run_eval(
    session: Session,
    provider: EmbeddingProvider,
    judgments: List[GroundTruthEntry],
    k: int = 10,
) -> EvalReport:
    per_query: Dict[str, Dict[str, MethodScores]] = {}
    relevance_lists_by_method: Dict[str, List[List[int]]] = {m.value: [] for m in _METHODS}
    excluded_count = 0

    for gt in judgments:
        if not gt.relevant_product_ids:
            logger.warning(f"Query {gt.query_id!r} has 0 relevant items in ground truth - excluding from aggregate")
            excluded_count += 1
            continue

        relevant_ids = set(gt.relevant_product_ids)
        per_query[gt.query_id] = {}

        for method in _METHODS:
            try:
                results, _, _ = search_hybrid(
                    session, gt.query, provider, method=method, limit=_SEARCH_LIMIT
                )
            except Exception as e:
                logger.warning(f"{method.value} search failed for query {gt.query_id!r}: {e}")
                results = []

            relevance = [1 if p.id in relevant_ids else 0 for p in results]
            relevance_lists_by_method[method.value].append(relevance)

            scores = MethodScores(
                ndcg_at_10=ndcg_at_k(relevance, k),
                precision_at_10=precision_at_k(relevance, k),
                mrr=reciprocal_rank(relevance),
            )
            per_query[gt.query_id][method.value] = scores

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
    )


def run_and_save_eval(
    session: Session,
    provider: EmbeddingProvider,
    judgments: List[GroundTruthEntry],
    ground_truth_source: str,
    output_prefix: str,
    k: int = 10,
) -> EvalReport:
    report = run_eval(session, provider, judgments, k=k)
    report.ground_truth_source = ground_truth_source
    save_report(f"{output_prefix}.json", f"{output_prefix}.md", report)
    return report
