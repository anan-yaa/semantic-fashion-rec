#!/usr/bin/env python3
"""
Ingest fashion product catalogue from HuggingFace dataset.

Usage:
    python3 scripts/ingest_catalogue.py [--dataset-path PATH] [--sample N]

Options:
    --dataset-path PATH  Path to HF dataset (default: use cached)
    --sample N           Process only N products for testing
"""

import argparse
import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_session
from app.services.ingestion import (
    ingest_records,
    load_dataset_from_cache,
    load_dataset_from_path,
)
from core.logging import setup_logging

logger = logging.getLogger(__name__)


def load_dataset(dataset_path: str | None = None):
    """
    Load HuggingFace dataset, removing the image column to save memory.

    Args:
        dataset_path: Optional path to dataset. If None, uses cached version.

    Returns:
        Dataset with image column removed.
    """
    if dataset_path:
        logger.info(f"Loading dataset from {dataset_path}")
        ds = load_dataset_from_path(dataset_path)
    else:
        logger.info("Loading cached HuggingFace dataset")
        ds = load_dataset_from_cache()

    logger.info(f"Loaded {len(ds)} products (image column removed)")
    return ds


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest fashion product catalogue from HuggingFace dataset"
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Path to HuggingFace dataset (default: use cached)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Process only N products for testing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for upserts (default: 100)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    try:
        # Load dataset
        dataset = load_dataset(args.dataset_path)

        # Limit to sample if requested
        if args.sample:
            logger.info(f"Processing sample of {args.sample} products")
            records = [dataset[i] for i in range(min(args.sample, len(dataset)))]
        else:
            records = dataset

        # Get session and ingest
        session = next(get_session())
        try:
            stats = ingest_records(session, records, batch_size=args.batch_size)
        finally:
            session.close()

        # Print summary
        print("\n" + "=" * 60)
        print("INGESTION SUMMARY")
        print("=" * 60)
        print(f"Inserted:  {stats.inserted}")
        print(f"Updated:   {stats.updated}")
        print(f"Skipped:   {stats.skipped}")
        print(f"Invalid:   {stats.invalid}")
        print(f"Total:     {stats.inserted + stats.updated + stats.skipped + stats.invalid}")
        print("=" * 60)

        return 0

    except Exception:
        logger.exception("Ingestion failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
