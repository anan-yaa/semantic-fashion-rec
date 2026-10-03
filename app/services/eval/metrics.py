"""Ranking quality metrics for search evaluation.

Pure functions over binary relevance lists (in ranked order, index 0 = rank
1) rather than DB objects - mirrors app/services/search/rank_fusion.py's
style, which keeps these trivially unit-testable in isolation.
"""
import math
from typing import List


def dcg_at_k(relevance: List[int], k: int) -> float:
    """Discounted Cumulative Gain at rank k.

    DCG = sum_{i=1}^{k} relevance[i-1] / log2(i + 1)
    """
    total = 0.0
    for i, rel in enumerate(relevance[:k], start=1):
        total += rel / math.log2(i + 1)
    return total


def ndcg_at_k(relevance: List[int], k: int) -> float:
    """Normalized DCG at rank k: dcg_at_k(relevance, k) / dcg_at_k(ideal, k).

    ideal = relevance sorted descending (all relevant items first). Returns
    0.0 (not NaN) when there are no relevant items at all, since ideal DCG
    is 0 and the ranking is undefined-but-trivially-uninformative in that case.
    """
    ideal = sorted(relevance, reverse=True)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0.0:
        return 0.0
    return dcg_at_k(relevance, k) / ideal_dcg


def precision_at_k(relevance: List[int], k: int) -> float:
    """Fraction of the top-k results that are relevant.

    A list shorter than k is treated as padded with non-relevant (0) items
    for the missing tail, rather than shrinking the denominator - a method
    that returns fewer than k results should not score higher just because
    the denominator got smaller.
    """
    if k <= 0:
        return 0.0
    top_k = relevance[:k]
    return sum(top_k) / k


def reciprocal_rank(relevance: List[int]) -> float:
    """1 / rank of the first relevant item (1-indexed); 0.0 if none are relevant."""
    for i, rel in enumerate(relevance, start=1):
        if rel:
            return 1.0 / i
    return 0.0


def mrr(relevance_lists: List[List[int]]) -> float:
    """Mean Reciprocal Rank across multiple queries' relevance lists."""
    if not relevance_lists:
        return 0.0
    return sum(reciprocal_rank(rel) for rel in relevance_lists) / len(relevance_lists)
