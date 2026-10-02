#!/usr/bin/env python3
"""Embed catalogue products using the embedding provider."""
import argparse
import logging
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.logging import setup_logging
from app.services.embedding import embed_products
from app.providers.factory import get_embedding_provider

setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Main entry point for embedding CLI."""
    parser = argparse.ArgumentParser(description="Embed fashion catalogue products")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum products to embed")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size for embedding")
    parser.add_argument("--model", type=str, help="Override embedding model name")
    args = parser.parse_args()

    # Create DB session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        # Get provider
        model = args.model or settings.embedding_model
        logger.info(f"Using model: {model}, batch size: {args.batch_size}")
        provider = get_embedding_provider(settings, use_fake=False)

        # Embed
        logger.info(f"Starting embedding run (limit={args.limit})")
        start_dt = datetime.utcnow()
        stats = embed_products(session, provider, limit=args.limit, batch_size=args.batch_size)
        elapsed = datetime.utcnow() - start_dt

        # Report
        logger.info(f"Embedding complete in {elapsed.total_seconds():.2f}s")
        logger.info(f"  Embedded: {stats.embedded_count}")
        logger.info(f"  Skipped: {stats.skipped_count}")
        logger.info(f"  Errors: {stats.error_count}")
        logger.info(f"  Total time: {stats.total_time_ms:.0f}ms")

        return 0 if stats.error_count == 0 else 1

    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
