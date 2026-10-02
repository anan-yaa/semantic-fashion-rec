"""Map HuggingFace records to internal Product schema."""

import uuid
from typing import Optional

from app.schemas.product import ProductIngestSchema, ProductCreateSchema
from app.services.ingestion.normalizer import normalize_text
from app.services.ingestion.hashing import compute_content_hash


def build_search_text(record: ProductIngestSchema) -> str:
    """
    Build deterministic search text from normalized HF fields.

    Field order is fixed to ensure consistency across runs:
    productDisplayName, gender, masterCategory, subCategory,
    articleType, baseColour, usage, season.

    Args:
        record: ProductIngestSchema instance.

    Returns:
        Space-separated normalized fields, or empty string if all None.
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

    search_text = " ".join(p for p in parts if p is not None)
    return search_text if search_text else ""


def map_record_to_product_schema(record: ProductIngestSchema) -> Optional[ProductCreateSchema]:
    """
    Map HuggingFace record to ProductCreateSchema.

    Dataset-specific field mapping:
    - id → external_product_id
    - productDisplayName → name (required)
    - masterCategory → category
    - subCategory → subcategory
    - gender → gender
    - baseColour → color
    - usage → style
    - season → season
    - articleType, year → attributes (JSON)
    - brand, material, price → NULL
    - currency → "USD" (default)

    Args:
        record: ProductIngestSchema instance.

    Returns:
        ProductCreateSchema if record is valid, None otherwise.
    """
    # productDisplayName is required
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
        brand=None,
        gender=record.gender,
        color=record.baseColour,
        material=None,
        style=record.usage,
        season=record.season,
        price=None,
        currency="USD",
        availability=True,
        attributes=attributes if attributes else None,
        search_text=search_text,
        content_hash=content_hash,
    )
