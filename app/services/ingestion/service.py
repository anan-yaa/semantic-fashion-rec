"""Ingestion service that orchestrates the complete pipeline."""

from typing import Optional
import logging

from sqlalchemy.orm import Session

from app.db.repositories.product_repository import ProductRepository
from app.db.models.product import Product
from app.schemas.product import ProductIngestSchema
from app.services.ingestion.mapper import map_record_to_product_schema

logger = logging.getLogger(__name__)


class IngestionStats:
    """Track ingestion statistics."""

    def __init__(self):
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self.invalid = 0
        self.reactivated = 0
        self.deactivated = 0

    def __repr__(self):
        return (
            f"IngestionStats(inserted={self.inserted}, updated={self.updated}, "
            f"skipped={self.skipped}, invalid={self.invalid}, "
            f"reactivated={self.reactivated}, deactivated={self.deactivated})"
        )


def map_schema_to_product_model(schema) -> Product:
    """Convert ProductCreateSchema to SQLAlchemy Product model."""
    return Product(
        id=schema.id,
        external_product_id=schema.external_product_id,
        name=schema.name,
        description=schema.description,
        category=schema.category,
        subcategory=schema.subcategory,
        brand=schema.brand,
        gender=schema.gender,
        color=schema.color,
        material=schema.material,
        style=schema.style,
        season=schema.season,
        price=schema.price,
        currency=schema.currency,
        availability=schema.availability,
        attributes=schema.attributes,
        search_text=schema.search_text,
        content_hash=schema.content_hash,
    )


def deactivate_missing_products(
    session: Session, present_external_ids: set, chunk_size: int = 1000
) -> int:
    """Mark available products whose external id is not in the feed as unavailable.

    Returns the number of products deactivated.
    """
    active_ids = {
        ext_id
        for (ext_id,) in session.query(Product.external_product_id).filter(
            Product.availability == True  # noqa: E712
        )
    }
    missing = sorted(active_ids - present_external_ids)
    for start in range(0, len(missing), chunk_size):
        chunk = missing[start : start + chunk_size]
        session.query(Product).filter(Product.external_product_id.in_(chunk)).update(
            {Product.availability: False}, synchronize_session=False
        )
    session.commit()
    return len(missing)


def ingest_records(
    session: Session,
    records: list,
    batch_size: int = 100,
    mark_missing_unavailable: bool = False,
) -> IngestionStats:
    """
    Ingest a list of records into the database.

    Processes records through the pipeline:
    1. Parse and validate (ProductIngestSchema)
    2. Map to internal schema
    3. Check if product exists
    4. Decide: insert (new), update (changed), or skip (unchanged);
       a previously unavailable product that reappears is made available again
    5. Batch upsert to database
    6. Optionally mark products absent from the feed as unavailable

    Args:
        session: SQLAlchemy session.
        records: List of record dictionaries from dataset.
        batch_size: Number of records per batch upsert.
        mark_missing_unavailable: Treat `records` as the complete catalogue and
            mark every product not in it as unavailable. Only pass True for a
            full feed, never a sample.

    Returns:
        IngestionStats with inserted/updated/skipped/invalid/reactivated/deactivated counts.
    """
    stats = IngestionStats()
    repo = ProductRepository(session)

    batch = []
    seen_external_ids = set()

    for idx, record_dict in enumerate(records):
        # Parse and validate
        try:
            record = ProductIngestSchema(**record_dict)
        except Exception as e:
            logger.warning(f"Record {idx} invalid: {e}")
            stats.invalid += 1
            continue

        # Check for duplicate external_product_id in this batch
        ext_id = str(record.id)
        if ext_id in seen_external_ids:
            logger.debug(f"Duplicate external_product_id {ext_id}, skipping")
            stats.invalid += 1
            continue
        seen_external_ids.add(ext_id)

        # Map to create schema
        create_schema = map_record_to_product_schema(record)
        if not create_schema:
            logger.warning(f"Record {idx} (id={record.id}) could not be mapped")
            stats.invalid += 1
            continue

        # Check if product exists in database
        existing = repo.get_by_external_id(ext_id)

        if existing is None:
            # New product
            stats.inserted += 1
            product = map_schema_to_product_model(create_schema)
            batch.append(product)
        elif existing.content_hash == create_schema.content_hash:
            if existing.availability:
                stats.skipped += 1
            else:
                stats.reactivated += 1
                existing.availability = True
                batch.append(existing)
        else:
            # Updated
            stats.updated += 1
            if not existing.availability:
                stats.reactivated += 1
                existing.availability = True
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
            logger.debug(f"Flushed batch of {len(batch)}")
            batch = []

    # Final batch
    if batch:
        repo.upsert_many(batch)
        logger.debug(f"Flushed final batch of {len(batch)}")

    if mark_missing_unavailable:
        if seen_external_ids:
            stats.deactivated = deactivate_missing_products(session, seen_external_ids)
        else:
            # An empty feed is almost certainly a broken download, not an empty catalogue.
            logger.error("Feed contained no records; refusing to mark the whole catalogue unavailable")

    return stats
