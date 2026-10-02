from app.services.ingestion.loader import (
    load_dataset_from_cache,
    load_dataset_from_path,
)
from app.services.ingestion.normalizer import normalize_text
from app.services.ingestion.hashing import compute_content_hash
from app.services.ingestion.mapper import (
    build_search_text,
    map_record_to_product_schema,
)
from app.services.ingestion.service import (
    IngestionStats,
    ingest_records,
    map_schema_to_product_model,
)

__all__ = [
    "load_dataset_from_cache",
    "load_dataset_from_path",
    "normalize_text",
    "compute_content_hash",
    "build_search_text",
    "map_record_to_product_schema",
    "map_schema_to_product_model",
    "IngestionStats",
    "ingest_records",
]
