"""Pure row-selection/shaping logic for the Colab embedding export.

Kept separate from scripts/export_embedding_batch.py's file I/O so the
selection and shaping logic can be unit tested without Parquet/pyarrow.
"""
from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.embedding.change_detector import get_products_needing_embedding


@dataclass
class ExportRow:
    """One row of the embedding export artifact."""
    id: str
    external_product_id: str
    content_hash: str
    search_text: str


def select_products_for_export(session: Session, limit: int = 100000) -> List[Product]:
    """Select products needing (re)embedding, in a deterministic order.

    Reuses the same change-detection query the live embedding job uses
    (embedding IS NULL OR embedding_content_hash IS DISTINCT FROM
    content_hash), so the export selects exactly what a local
    `embed_catalogue.py` run would have picked up. Results are sorted by
    (created_at, id) - a stable, deterministic tie-breaker on top of the
    underlying query's ORDER BY created_at - so repeated exports of an
    unchanged catalogue always produce byte-identical row ordering.
    """
    products = get_products_needing_embedding(session, limit=limit)
    return sorted(products, key=lambda p: (p.created_at, p.id))


def to_export_rows(products: List[Product]) -> List[ExportRow]:
    """Shape Product rows into the export artifact schema.

    Products with no search_text are skipped (there is nothing to embed)
    rather than exported with an empty string, mirroring how
    app/services/embedding/service.py:embed_products already treats them.
    """
    rows = []
    for p in products:
        if not p.search_text:
            continue
        rows.append(
            ExportRow(
                id=p.id,
                external_product_id=p.external_product_id,
                content_hash=p.content_hash,
                search_text=p.search_text,
            )
        )
    return rows
