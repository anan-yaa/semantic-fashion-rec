#!/usr/bin/env python3
"""Sync the search index with the latest catalogue feed in one step.

1. Ingest the full feed: insert new products, update changed ones, reactivate
   returning ones, and mark products missing from the feed as unavailable.
2. Embed only new/changed products (content_hash differs from embedded hash).
3. Rebuild the keyword index only for new/changed products.

Safe to re-run: an unchanged feed does no embedding or indexing work.

Usage:
    PYTHONPATH=. python3 scripts/sync_catalogue.py [--dataset-path PATH]
"""
import argparse
import logging
import sys

from app.db.database import get_session
from app.providers.factory import get_embedding_provider
from app.services.embedding import embed_products
from app.services.ingestion import ingest_records, load_dataset_from_cache, load_dataset_from_path
from app.services.keyword_index import build_keyword_index
from core.config import settings
from core.logging import setup_logging

logger = logging.getLogger(__name__)

CHUNK = 5000


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync catalogue: ingest, embed, index")
    parser.add_argument("--dataset-path", type=str, default=None, help="Path to dataset (default: cached HF dataset)")
    args = parser.parse_args()
    setup_logging()

    dataset = load_dataset_from_path(args.dataset_path) if args.dataset_path else load_dataset_from_cache()
    session = next(get_session())
    try:
        ingest = ingest_records(session, dataset, mark_missing_unavailable=True)
        logger.info(f"Ingest: {ingest}")

        provider = get_embedding_provider(settings, use_fake=False)
        embedded = embed_errors = 0
        while True:
            stats = embed_products(session, provider, limit=CHUNK, batch_size=settings.embedding_batch_size)
            embedded += stats.embedded_count
            embed_errors += stats.error_count
            if stats.embedded_count == 0:
                break
        logger.info(f"Embed: embedded={embedded} errors={embed_errors}")

        indexed = 0
        while True:
            stats = build_keyword_index(session, limit=CHUNK)
            indexed += stats.indexed_count
            if stats.indexed_count == 0:
                break
        logger.info(f"Keyword index: indexed={indexed}")

        print(
            f"\nSync complete: inserted={ingest.inserted} updated={ingest.updated} "
            f"reactivated={ingest.reactivated} deactivated={ingest.deactivated} "
            f"unchanged={ingest.skipped} invalid={ingest.invalid} | "
            f"embedded={embedded} embed_errors={embed_errors} | indexed={indexed}"
        )
        return 0 if embed_errors == 0 else 1
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
