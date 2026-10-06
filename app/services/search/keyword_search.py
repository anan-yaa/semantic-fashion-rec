"""Full-text keyword search."""
import logging
import math
from typing import List, Optional, Tuple

from sqlalchemy import Integer, Text, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.schemas.search import SearchFilter
from app.services.search.product_types import ARTICLE_TYPE
from app.services.timing import timed

logger = logging.getLogger(__name__)


def search_keyword(
    session: Session,
    query_text: str,
    filters: Optional[SearchFilter] = None,
    limit: int = 50,
    min_term_coverage: float = 0.0,
    article_types: Optional[List[str]] = None,
) -> Tuple[List[Product], int]:
    """Search using keyword matching.

    On PostgreSQL, uses TSVECTOR full-text search: plainto_tsquery() to parse
    the query, with its terms OR-ed so partial matches are returned, and
    ts_rank() to rank by relevance, backed by the GIN index on search_vector.
    On SQLite, falls back to ILIKE pattern matching (no tsvector support).

    Args:
        session: Database session.
        query_text: Search query.
        filters: Optional search filters.
        limit: Maximum results to return.
        min_term_coverage: Minimum fraction of the query's terms a product must
            match (PostgreSQL only). 0.0 keeps any partial match; hybrid search
            raises it so single-word hits on multi-word queries (e.g. only
            "black" for "black leather jacket") don't get fused in as noise.
        article_types: Optional list of product types (attributes.articleType) to restrict to.

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
    if article_types:
        query_obj = query_obj.filter(ARTICLE_TYPE.in_(article_types))

    # PostgreSQL FTS using TSVECTOR, OR-ed tsquery, ts_rank
    if dialect == "postgresql":
        # plainto_tsquery ANDs every term, so natural-language queries like
        # "black leather jacket" matched nothing when no single product has all
        # three words. OR the parsed (stemmed, stopword-free) lexemes instead;
        # ts_rank scores products matching more query terms higher, so full
        # matches still come first.
        tsquery = func.to_tsquery(
            "english",
            func.replace(cast(func.plainto_tsquery("english", query_text), Text), "&", "|"),
        )
        query_obj = query_obj.filter(Product.search_vector.op("@@")(tsquery))

        if min_term_coverage > 0:
            # Same parsing as plainto_tsquery: stemmed, stopword-free lexemes
            with timed("keyword_db"):
                lexemes = session.execute(
                    select(func.tsvector_to_array(func.to_tsvector("english", query_text)))
                ).scalar() or []
            if lexemes:
                # Lexemes are already stemmed, so match them with 'simple' to
                # avoid stemming them a second time
                matched_terms = sum(
                    cast(
                        Product.search_vector.op("@@")(
                            func.to_tsquery("simple", func.quote_literal(lexeme))
                        ),
                        Integer,
                    )
                    for lexeme in lexemes
                )
                required = math.ceil(min_term_coverage * len(lexemes))
                query_obj = query_obj.filter(matched_terms >= required)

        query_obj = query_obj.order_by(
            desc(func.ts_rank(Product.search_vector, tsquery)),
            Product.id,  # Deterministic tiebreaker for stable ordering of tied ranks
        )

        with timed("keyword_db"):
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

    with timed("keyword_db"):
        total_count = query_obj.count()
        results = query_obj.limit(limit).all()

    return results, total_count
