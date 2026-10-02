"""Orchestrates embedding generation and persistence."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.providers.base import EmbeddingProvider
from app.db.models.product import Product
from app.db.repositories.product_repository import ProductRepository
from app.services.embedding.change_detector import get_products_needing_embedding

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingStats:
    """Statistics from an embedding run."""
    embedded_count: int
    skipped_count: int
    error_count: int
    total_time_ms: float


def get_unembedded_products(session: Session, limit: int = 1000) -> List[Product]:
    """Get products that need embedding.

    Args:
        session: Database session.
        limit: Maximum number of products to return.

    Returns:
        List of Product objects needing embedding.
    """
    return get_products_needing_embedding(session, limit)


def embed_products(
    session: Session,
    provider: EmbeddingProvider,
    limit: int = 10000,
    batch_size: int = 64,
) -> EmbeddingStats:
    """Embed products and persist embeddings.

    Args:
        session: Database session.
        provider: EmbeddingProvider instance.
        limit: Maximum number of products to process.
        batch_size: Batch size for embedding (provider will handle batching).

    Returns:
        EmbeddingStats with results.
    """
    import time
    start_time = time.time()

    repo = ProductRepository(session)
    embedded_count = 0
    error_count = 0
    skipped_count = 0

    # Get products needing embedding
    products = get_products_needing_embedding(session, limit=limit)
    logger.info(f"Found {len(products)} products needing embedding")

    if not products:
        elapsed_ms = (time.time() - start_time) * 1000
        return EmbeddingStats(0, 0, 0, elapsed_ms)

    # Collect all search texts
    search_texts = []
    product_ids = []
    for p in products:
        if p.search_text:
            search_texts.append(p.search_text)
            product_ids.append(p.id)
        else:
            skipped_count += 1

    if not search_texts:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"No search texts to embed. Skipped: {skipped_count}")
        return EmbeddingStats(0, skipped_count, 0, elapsed_ms)

    # Embed all texts at once
    try:
        embeddings = provider.embed_passages(search_texts)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        elapsed_ms = (time.time() - start_time) * 1000
        return EmbeddingStats(0, skipped_count, len(search_texts), elapsed_ms)

    # Persist embeddings
    now = datetime.utcnow()
    for product_id, embedding in zip(product_ids, embeddings):
        try:
            product = session.query(Product).filter_by(id=product_id).first()
            if product:
                product.embedding = embedding
                product.embedding_content_hash = product.content_hash
                product.embedded_at = now
                embedded_count += 1
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            error_count += 1

    # Commit all changes
    try:
        session.commit()
        logger.info(f"Embedded {embedded_count} products, {error_count} errors, {skipped_count} skipped")
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        session.rollback()
        error_count += embedded_count  # Count as errors since they weren't persisted
        embedded_count = 0

    elapsed_ms = (time.time() - start_time) * 1000
    return EmbeddingStats(embedded_count, skipped_count, error_count, elapsed_ms)
