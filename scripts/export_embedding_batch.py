#!/usr/bin/env python3
"""Export products needing (re)embedding to a Parquet file for Colab.

This is read-only against the local database: it selects the same set of
products app/services/embedding/service.py:embed_products would embed
locally, and writes them to a portable artifact instead of calling an
embedding provider. Run scripts/import_embeddings.py afterwards to bring
the Colab-computed embeddings back in.

Output schema (Parquet):
    id                    string  internal UUID, re-import identity cross-check
    external_product_id   string  stable identifier used for re-import matching
    content_hash          string  hash at export time
    search_text           string  raw text to embed (Colab applies the
                                   "passage: " prefix itself)
"""
import argparse
import logging
import sys

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.embedding.export import select_products_for_export, to_export_rows
from core.config import settings
from core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export products needing embedding to Parquet")
    parser.add_argument("--output", type=str, required=True, help="Output Parquet file path")
    parser.add_argument("--limit", type=int, default=100000, help="Maximum products to export")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        products = select_products_for_export(session, limit=args.limit)
        rows = to_export_rows(products)

        if not rows:
            logger.info("No products need embedding - nothing to export")
            return 0

        df = pd.DataFrame(
            {
                "id": [r.id for r in rows],
                "external_product_id": [r.external_product_id for r in rows],
                "content_hash": [r.content_hash for r in rows],
                "search_text": [r.search_text for r in rows],
            }
        )
        df.to_parquet(args.output, index=False)

        logger.info(f"Exported {len(rows)} products needing embedding to {args.output}")
        logger.info(f"Skipped (no search_text): {len(products) - len(rows)}")
        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
