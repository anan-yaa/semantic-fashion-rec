#!/usr/bin/env python3
"""Import Colab-computed embeddings from a Parquet file into PostgreSQL.

Reads the result artifact produced by the Colab notebook
(colab/compute_embeddings_colab.ipynb) and writes embedding,
embedding_content_hash, and embedded_at onto the matching local products.

Matching and safety (see app/services/embedding/import_validation.py):
    - products are matched by external_product_id (stable, unique)
    - the artifact's own id column is cross-checked against the resolved
      product's id; a mismatch is refused rather than written
    - an embedding is only written if its artifact content_hash still
      matches the product's CURRENT content_hash - if the product changed
      locally since export, the row is skipped (content_hash_mismatch),
      not overwritten, so it will simply be picked up by the next
      embedding run instead
    - rows whose embedding_content_hash is already up to date are skipped
      as no-ops, making repeated imports of the same artifact idempotent

Updates are applied in batches (bulk_update_mappings + chunked commits),
not one transaction per product.

Input schema (Parquet):
    id                    string              internal UUID (cross-check)
    external_product_id   string              match key
    content_hash          string              hash that was embedded
    embedding             list<float32>[768]  L2-normalized embedding
"""
import argparse
import logging
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.logging import setup_logging
from app.db.models.product import Product
from app.services.embedding.import_validation import (
    ArtifactRow,
    ImportOutcome,
    LocalProductRecord,
    classify_row,
)

setup_logging()
logger = logging.getLogger(__name__)


def load_local_products_by_external_id(session) -> dict:
    """One query, loading just the fields needed to validate every row."""
    rows = session.query(
        Product.id, Product.external_product_id, Product.content_hash, Product.embedding_content_hash
    ).all()
    return {
        external_product_id: LocalProductRecord(
            id=pid, content_hash=content_hash, embedding_content_hash=embedding_content_hash
        )
        for pid, external_product_id, content_hash, embedding_content_hash in rows
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Colab-computed embeddings from Parquet")
    parser.add_argument("--input", type=str, required=True, help="Input Parquet file path")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per DB commit")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    required_cols = {"id", "external_product_id", "content_hash", "embedding"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        logger.error(f"Input file missing required columns: {sorted(missing_cols)}")
        return 1

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    counts = {outcome: 0 for outcome in ImportOutcome}
    failure_reasons = []
    mismatch_reasons = []

    try:
        local_products = load_local_products_by_external_id(session)
        logger.info(f"Loaded {len(local_products)} local products for validation")
        logger.info(f"Processing {len(df)} rows from {args.input}")

        pending_updates = []
        now = datetime.now(timezone.utc)

        for row in df.itertuples(index=False):
            artifact_row = ArtifactRow(
                id=str(row.id),
                external_product_id=row.external_product_id,
                content_hash=row.content_hash,
                embedding=row.embedding,
            )
            decision = classify_row(artifact_row, local_products)
            counts[decision.outcome] += 1

            if decision.outcome == ImportOutcome.FAILURE:
                failure_reasons.append(decision.reason)
            elif decision.outcome == ImportOutcome.CONTENT_HASH_MISMATCH:
                mismatch_reasons.append(decision.reason)
            elif decision.outcome == ImportOutcome.IMPORTED:
                payload = dict(decision.update_payload)
                payload["embedded_at"] = now
                pending_updates.append(payload)

            if len(pending_updates) >= args.batch_size:
                session.bulk_update_mappings(Product, pending_updates)
                session.commit()
                pending_updates = []

        if pending_updates:
            session.bulk_update_mappings(Product, pending_updates)
            session.commit()

        logger.info("Import complete")
        logger.info(f"  Imported:               {counts[ImportOutcome.IMPORTED]}")
        logger.info(f"  Skipped (up to date):   {counts[ImportOutcome.SKIPPED]}")
        logger.info(f"  Missing products:       {counts[ImportOutcome.MISSING_PRODUCT]}")
        logger.info(f"  Content hash mismatches:{counts[ImportOutcome.CONTENT_HASH_MISMATCH]}")
        logger.info(f"  Invalid embeddings:     {counts[ImportOutcome.INVALID_EMBEDDING]}")
        logger.info(f"  Failures:               {counts[ImportOutcome.FAILURE]}")

        if mismatch_reasons:
            logger.warning(f"First content_hash mismatch: {mismatch_reasons[0]}")
        if failure_reasons:
            for reason in failure_reasons[:10]:
                logger.error(f"Failure: {reason}")

        return 0 if counts[ImportOutcome.FAILURE] == 0 else 1

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
