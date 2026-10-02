"""Full-text keyword search."""
import logging
from typing import List, Optional, Tuple

from sqlalchemy import or_, desc, func
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.schemas.search import SearchFilter

logger = logging.getLogger(__name__)


def search_keyword(
    session: Session,
    query_text: str,
    filters: Optional[SearchFilter] = None,
    limit: int = 50,
) -> Tuple[List[Product], int]:
    """Search using keyword matching.

    On PostgreSQL, uses TSVECTOR full-text search: plainto_tsquery() to parse
    the query and ts_rank_cd() to rank by relevance, backed by the GIN index
    on search_vector.
    On SQLite, falls back to ILIKE pattern matching (no tsvector support).

    Args:
        session: Database session.
        query_text: Search query.
        filters: Optional search filters.
        limit: Maximum results to return.

    Returns:
        Tuple of (products, total_count).
    """
    dialect = session.bind.dialect.name

    # Build base query
    query_obj = session.query(Product)

    # Apply filters first
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

    # PostgreSQL FTS using TSVECTOR, plainto_tsquery, ts_rank_cd
    if dialect == "postgresql":
        tsquery = func.plainto_tsquery("english", query_text)
        query_obj = query_obj.filter(
            Product.search_vector.op("@@")(tsquery)
        ).order_by(
            desc(func.ts_rank_cd(Product.search_vector, tsquery))
        )

        total_count = query_obj.count()
        results = query_obj.limit(limit).all()
        return results, total_count

    # Fallback to ILIKE (SQLite compatible, no tsvector support there)
    tokens = query_text.lower().split()
    conditions = []
    for token in tokens:
        pattern = f"%{token}%"
        conditions.append(Product.name.ilike(pattern))
        conditions.append(Product.search_text.ilike(pattern))

    if conditions:
        query_obj = query_obj.filter(or_(*conditions))

    total_count = query_obj.count()
    results = query_obj.limit(limit).all()

    return results, total_count
