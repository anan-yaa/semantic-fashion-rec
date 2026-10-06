"""Vector similarity search."""
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc, text

from app.db.models.product import Product
from app.providers.base import EmbeddingProvider
from app.schemas.search import SearchFilter
from app.services.search.product_types import ARTICLE_TYPE
from app.services.timing import timed

logger = logging.getLogger(__name__)


def search_vector(
    session: Session,
    query_text: str,
    provider: EmbeddingProvider,
    filters: Optional[SearchFilter] = None,
    limit: int = 50,
    article_types: Optional[List[str]] = None,
) -> Tuple[List[Product], int]:
    """Search using vector similarity.

    Args:
        session: Database session.
        query_text: Search query.
        provider: EmbeddingProvider to embed the query.
        filters: Optional search filters.
        limit: Maximum results to return.
        article_types: Optional list of product types (attributes.articleType) to restrict to.

    Returns:
        Tuple of (products, total_count).
    """
    # Embed the query
    with timed("embed"):
        query_embedding = provider.embed_queries([query_text])[0]

    # Start with products that have embeddings
    query_obj = session.query(Product).filter(Product.embedding.isnot(None))

    # Apply filters
    if filters:
        if filters.category:
            query_obj = query_obj.filter_by(category=filters.category)
        if filters.gender:
            query_obj = query_obj.filter_by(gender=filters.gender)
        if filters.color:
            query_obj = query_obj.filter_by(color=filters.color)
        if filters.season:
            query_obj = query_obj.filter_by(season=filters.season)
        if filters.availability is not None:
            query_obj = query_obj.filter_by(availability=filters.availability)
    if article_types:
        query_obj = query_obj.filter(ARTICLE_TYPE.in_(article_types))
    if session.bind.dialect.name == "postgresql":
        # The HNSW index returns its nearest ~40 candidates and only then
        # applies the WHERE clause, so a selective type filter (258 jackets of
        # 44k products) can come back nearly empty; iterative scan keeps
        # searching until enough rows pass. Set on every call because SET LOCAL
        # lasts for the whole transaction and would otherwise leak into later
        # unfiltered searches.
        mode = "strict_order" if article_types else "off"
        session.execute(text(f"SET LOCAL hnsw.iterative_scan = {mode}"))

    with timed("vector_db"):
        total_count = query_obj.count()

        # Vector similarity ranking (using cosine distance <=>)
        # Note: On SQLite this won't work; on PostgreSQL it uses HNSW index
        try:
            ranked = query_obj.order_by(
                Product.embedding.cosine_distance(query_embedding)
            ).limit(limit).all()
        except Exception as e:
            logger.debug(f"Vector search failed (expected on SQLite): {e}, falling back to empty")
            ranked = []

    return ranked, total_count


def calculate_similarity_score(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity score (0-1, higher is more similar).
    """
    if not vec1 or not vec2:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))

    # Assume normalized vectors, so magnitude = 1
    # But compute just in case
    mag1 = sum(a**2 for a in vec1) ** 0.5
    mag2 = sum(b**2 for b in vec2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)
