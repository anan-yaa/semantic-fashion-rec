#!/usr/bin/env python3
"""Build keyword index using PostgreSQL TSVECTOR."""
import argparse
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.keyword_index import build_keyword_index
from core.config import settings
from core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Main entry point for keyword indexing CLI."""
    parser = argparse.ArgumentParser(description="Build keyword index for products")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum products to index")
    args = parser.parse_args()

    # Create DB session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        logger.info(f"Building keyword index (limit={args.limit})")
        start_dt = datetime.now(timezone.utc)
        stats = build_keyword_index(session, limit=args.limit)
        elapsed = datetime.now(timezone.utc) - start_dt

        logger.info(f"Keyword indexing complete in {elapsed.total_seconds():.2f}s")
        logger.info(f"  Indexed: {stats.indexed_count}")
        logger.info(f"  Skipped: {stats.skipped_count}")
        logger.info(f"  Total time: {stats.total_time_ms:.0f}ms")

        return 0

    except Exception:
        logger.exception("Keyword indexing failed")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
