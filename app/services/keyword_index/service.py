"""Keyword indexing using PostgreSQL TSVECTOR."""
import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


@dataclass
class KeywordIndexStats:
    """Statistics from a keyword indexing run."""
    indexed_count: int
    skipped_count: int
    total_time_ms: float


def build_keyword_index(session: Session, limit: int = 10000) -> KeywordIndexStats:
    """Build TSVECTOR keyword index for products.

    Updates search_vector and search_indexed_hash for products where:
    - search_vector IS NULL, OR
    - search_indexed_hash IS DISTINCT FROM content_hash (changed since last index)

    Uses PostgreSQL native to_tsvector in a single set-based UPDATE.

    Args:
        session: Database session (must be PostgreSQL).
        limit: Maximum products to index in this run.

    Returns:
        KeywordIndexStats with results.
    """
    start_time = time.time()

    try:
        dialect = session.bind.dialect.name
        if dialect != "postgresql":
            logger.warning(f"Keyword indexing not supported on {dialect}, skipping")
            return KeywordIndexStats(0, 0, 0)

        # Count products needing indexing, bounded by limit (matches what the
        # UPDATE below will actually touch).
        count_sql = text("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM products
                WHERE search_text IS NOT NULL
                AND (search_vector IS NULL OR search_indexed_hash IS DISTINCT FROM content_hash)
                LIMIT :limit
            ) AS to_index
        """)
        result = session.execute(count_sql, {"limit": limit})
        total_to_index = result.scalar() or 0

        if total_to_index == 0:
            logger.info("No products need keyword indexing")
            return KeywordIndexStats(0, 0, 0)

        logger.info(f"Indexing {total_to_index} products")

        # Single set-based UPDATE. PostgreSQL's UPDATE has no LIMIT clause,
        # so the affected rows are bounded via a ctid subquery (ctid is
        # PostgreSQL's physical row identifier, safe to use within one
        # statement since no concurrent writes to these rows are expected).
        update_sql = text("""
            UPDATE products
            SET
                search_vector = to_tsvector('english', search_text),
                search_indexed_hash = content_hash
            WHERE ctid IN (
                SELECT ctid FROM products
                WHERE search_text IS NOT NULL
                AND (search_vector IS NULL OR search_indexed_hash IS DISTINCT FROM content_hash)
                LIMIT :limit
            )
        """)

        result = session.execute(update_sql, {"limit": limit})
        indexed_count = result.rowcount or 0
        skipped_count = total_to_index - indexed_count

        session.commit()

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Indexed {indexed_count} products in {elapsed_ms:.0f}ms")

        return KeywordIndexStats(indexed_count, skipped_count, elapsed_ms)

    except Exception as e:
        logger.error(f"Keyword indexing failed: {e}", exc_info=True)
        session.rollback()
        elapsed_ms = (time.time() - start_time) * 1000
        return KeywordIndexStats(0, 0, elapsed_ms)
