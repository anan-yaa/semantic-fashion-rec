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
import sys
import logging
from typing import Optional
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import load_dataset

from core.config import settings
from core.logging import setup_logging
from app.db.database import get_session
from app.db.repositories.product_repository import ProductRepository
from app.schemas.product import ProductIngestSchema
from app.services.ingestion_service import (
    map_to_product_create_schema,
    schema_to_product_model,
    IngestionStats,
)

logger = logging.getLogger(__name__)


def load_hf_dataset(dataset_path: Optional[str] = None):
    """
    Load HuggingFace dataset, removing the image column to save memory.

    Args:
        dataset_path: Optional path to dataset. If None, uses cached version.

    Returns:
        Dataset with image column removed.
    """
    if dataset_path:
        logger.info(f"Loading dataset from {dataset_path}")
        ds = load_dataset(dataset_path, split="train", trust_remote_code=False)
    else:
        logger.info("Loading cached HuggingFace dataset")
        ds = load_dataset("HEBA2002/fashion-product-images-small", split="train", trust_remote_code=False)

    # Remove image column to avoid loading into memory
    cols_to_keep = [
        "id",
        "gender",
        "masterCategory",
        "subCategory",
        "articleType",
        "baseColour",
        "season",
        "year",
        "usage",
        "productDisplayName",
    ]
    ds = ds.select_columns(cols_to_keep)
    logger.info(f"Loaded {len(ds)} products (image column removed)")
    return ds


def ingest_products(
    dataset,
    sample_size: Optional[int] = None,
    batch_size: int = 100,
) -> IngestionStats:
    """
    Ingest products from dataset to database.

    Args:
        dataset: HuggingFace Dataset object.
        sample_size: If set, process only this many products.
        batch_size: Number of products per batch upsert.

    Returns:
        IngestionStats with counts.
    """
    stats = IngestionStats()

    # Limit dataset if sample_size provided
    if sample_size:
        dataset = dataset.select(range(min(sample_size, len(dataset))))
        logger.info(f"Processing sample of {len(dataset)} products")

    total = len(dataset)
    logger.info(f"Starting ingestion of {total} products")

    session = next(get_session())
    try:
        repo = ProductRepository(session)

        # Process in batches
        batch = []
        seen_external_ids = set()

        for idx, record_dict in enumerate(dataset):
            # Parse and validate
            try:
                record = ProductIngestSchema(**record_dict)
            except Exception as e:
                logger.warning(f"Record {idx} invalid: {e}")
                stats.invalid += 1
                continue

            # Check for duplicate external_product_id
            ext_id = str(record.id)
            if ext_id in seen_external_ids:
                logger.debug(f"Duplicate external_product_id {ext_id}, skipping")
                stats.invalid += 1
                continue
            seen_external_ids.add(ext_id)

            # Map to create schema
            create_schema = map_to_product_create_schema(record)
            if not create_schema:
                logger.warning(f"Record {idx} (id={record.id}) could not be mapped")
                stats.invalid += 1
                continue

            # Check if product exists
            existing = repo.get_by_external_id(ext_id)

            if existing is None:
                # New product
                stats.inserted += 1
                product = schema_to_product_model(create_schema)
                batch.append(product)
            elif existing.content_hash == create_schema.content_hash:
                # Unchanged
                stats.skipped += 1
            else:
                # Updated
                stats.updated += 1
                existing.name = create_schema.name
                existing.description = create_schema.description
                existing.category = create_schema.category
                existing.subcategory = create_schema.subcategory
                existing.gender = create_schema.gender
                existing.color = create_schema.color
                existing.style = create_schema.style
                existing.season = create_schema.season
                existing.attributes = create_schema.attributes
                existing.search_text = create_schema.search_text
                existing.content_hash = create_schema.content_hash
                batch.append(existing)

            # Flush batch if full
            if len(batch) >= batch_size:
                repo.upsert_many(batch)
                logger.debug(f"Flushed batch of {len(batch)} at record {idx}/{total}")
                batch = []

            # Progress
            if (idx + 1) % 1000 == 0:
                logger.info(
                    f"Progress: {idx + 1}/{total} | "
                    f"Inserted: {stats.inserted}, Updated: {stats.updated}, "
                    f"Skipped: {stats.skipped}, Invalid: {stats.invalid}"
                )

        # Final batch
        if batch:
            repo.upsert_many(batch)
            logger.debug(f"Flushed final batch of {len(batch)}")
    finally:
        session.close()

    logger.info(f"Ingestion complete: {stats}")
    return stats


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
        dataset = load_hf_dataset(args.dataset_path)

        # Ingest
        stats = ingest_products(
            dataset,
            sample_size=args.sample,
            batch_size=args.batch_size,
        )

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

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
