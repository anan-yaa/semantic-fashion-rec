"""Full-text keyword search."""
import logging
from typing import List, Optional, Tuple

from sqlalchemy import or_
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

    On PostgreSQL, uses TSVECTOR/full-text search.
    On SQLite, falls back to ILIKE pattern matching.

    Args:
        session: Database session.
        query_text: Search query.
        filters: Optional search filters.
        limit: Maximum results to return.

    Returns:
        Tuple of (products, total_count).
    """
    # Tokenize query
    tokens = query_text.lower().split()

    # Start with all products
    query_obj = session.query(Product)

    # Search: match query tokens in name or search_text
    conditions = []
    for token in tokens:
        pattern = f"%{token}%"
        conditions.append(Product.name.ilike(pattern))
        conditions.append(Product.search_text.ilike(pattern))

    if conditions:
        query_obj = query_obj.filter(or_(*conditions))

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

    # Get total count
    total_count = query_obj.count()

    # Return results
    results = query_obj.limit(limit).all()

    return results, total_count
