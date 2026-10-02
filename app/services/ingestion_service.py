import hashlib
import uuid
from typing import Optional

from app.db.models.product import Product
from app.schemas.product import ProductIngestSchema, ProductCreateSchema


def normalize_text(text: Optional[str]) -> Optional[str]:
    """
    Normalize text for deterministic hashing and search.
    - Strip whitespace
    - Lowercase
    - Collapse repeated whitespace
    Returns None if input is None or empty after normalization.
    """
    if not text:
        return None
    normalized = " ".join(str(text).lower().split())
    return normalized if normalized else None


def build_search_text(record: ProductIngestSchema) -> str:
    """
    Build deterministic search text from normalized HF fields.
    Order is fixed to ensure consistency across runs.
    """
    parts = []

    if record.productDisplayName:
        parts.append(normalize_text(record.productDisplayName))
    if record.gender:
        parts.append(normalize_text(record.gender))
    if record.masterCategory:
        parts.append(normalize_text(record.masterCategory))
    if record.subCategory:
        parts.append(normalize_text(record.subCategory))
    if record.articleType:
        parts.append(normalize_text(record.articleType))
    if record.baseColour:
        parts.append(normalize_text(record.baseColour))
    if record.usage:
        parts.append(normalize_text(record.usage))
    if record.season:
        parts.append(normalize_text(record.season))

    # Filter out None values and join
    search_text = " ".join(p for p in parts if p is not None)
    return search_text if search_text else ""


def compute_content_hash(search_text: str) -> str:
    """Compute SHA256 hash of search text for idempotent deduplication."""
    return hashlib.sha256(search_text.encode()).hexdigest()


def map_to_product_create_schema(record: ProductIngestSchema) -> Optional[ProductCreateSchema]:
    """
    Map HuggingFace record to ProductCreateSchema.
    Validates that productDisplayName (mapped to name) is present.
    Returns None if validation fails.
    """
    if not record.productDisplayName:
        return None

    search_text = build_search_text(record)
    if not search_text:
        return None

    content_hash = compute_content_hash(search_text)

    # Preserve articleType and year in attributes
    attributes = {}
    if record.articleType:
        attributes["articleType"] = record.articleType
    if record.year is not None:
        attributes["year"] = record.year

    return ProductCreateSchema(
        id=str(uuid.uuid4()),
        external_product_id=str(record.id),
        name=record.productDisplayName,
        description=None,
        category=record.masterCategory,
        subcategory=record.subCategory,
        brand=None,  # Not in HF dataset
        gender=record.gender,
        color=record.baseColour,
        material=None,  # Not in HF dataset
        style=record.usage,
        season=record.season,
        price=None,  # Not in HF dataset
        currency="USD",  # Default for missing data
        availability=True,
        attributes=attributes if attributes else None,
        search_text=search_text,
        content_hash=content_hash,
    )


def schema_to_product_model(schema: ProductCreateSchema) -> Product:
    """Convert ProductCreateSchema to SQLAlchemy Product model instance."""
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


class IngestionStats:
    """Track ingestion statistics."""

    def __init__(self):
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self.invalid = 0

    def __repr__(self):
        return (
            f"IngestionStats(inserted={self.inserted}, updated={self.updated}, "
            f"skipped={self.skipped}, invalid={self.invalid})"
        )
