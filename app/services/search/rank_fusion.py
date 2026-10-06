"""Reciprocal Rank Fusion for combining search results."""

from app.db.models.product import Product


def reciprocal_rank_fusion(
    vector_results: list[Product],
    keyword_results: list[Product],
    k: int = 60,
) -> list[Product]:
    """Fuse ranked results using Reciprocal Rank Fusion (RRF).

    RRF formula: score = 1 / (k + rank)
    Combines scores from both methods and re-ranks.

    Args:
        vector_results: Products ranked by vector similarity (higher relevance first).
        keyword_results: Products ranked by keyword match (higher relevance first).
        k: Constant for RRF formula (default 60, prevents overflow on small result sets).

    Returns:
        Fused and re-ranked product list.
    """
    # Build score dictionaries: product_id -> score
    scores: dict[str, float] = {}

    # Add vector search scores
    for rank, product in enumerate(vector_results, start=1):
        score = 1.0 / (k + rank)
        scores[product.id] = scores.get(product.id, 0) + score

    # Add keyword search scores
    for rank, product in enumerate(keyword_results, start=1):
        score = 1.0 / (k + rank)
        scores[product.id] = scores.get(product.id, 0) + score

    # Deduplicate: keep first occurrence, use combined score for ordering
    seen = set()
    fused_results = []

    # Start with high-scoring results from either method
    # Collect all products with their scores
    all_products = {}
    for p in vector_results:
        all_products[p.id] = p
    for p in keyword_results:
        all_products[p.id] = p

    # Sort by score (highest first)
    sorted_ids = sorted(scores.keys(), key=lambda pid: scores[pid], reverse=True)

    for product_id in sorted_ids:
        if product_id not in seen:
            fused_results.append(all_products[product_id])
            seen.add(product_id)

    return fused_results
