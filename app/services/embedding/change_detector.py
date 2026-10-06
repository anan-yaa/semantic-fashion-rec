"""Detect products that need (re)embedding based on content changes."""
from sqlalchemy.orm import Session

from app.db.models.product import Product


def get_products_needing_embedding(session: Session, limit: int = 1000) -> list[Product]:
    """Get products that need embedding.

    A product needs embedding if:
    - embedding IS NULL (new product), OR
    - embedding_content_hash IS DISTINCT FROM content_hash (changed product)

    Args:
        session: Database session.
        limit: Maximum number of products to return.

    Returns:
        List of Product objects needing embedding.
    """
    query = session.query(Product).filter(
        (Product.embedding.is_(None)) |
        (Product.embedding_content_hash != Product.content_hash)
    ).order_by(Product.created_at).limit(limit)

    return query.all()


def count_products_needing_embedding(session: Session) -> int:
    """Count products that need embedding.

    Args:
        session: Database session.

    Returns:
        Count of products needing embedding.
    """
    return session.query(Product).filter(
        (Product.embedding.is_(None)) |
        (Product.embedding_content_hash != Product.content_hash)
    ).count()
