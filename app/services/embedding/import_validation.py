"""Pure validation/classification logic for importing Colab-computed embeddings.

Kept separate from scripts/import_embeddings.py's DB/Parquet I/O so the
data-integrity rules (the part that actually matters) can be unit tested
without Postgres or pyarrow.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ImportOutcome(str, Enum):
    IMPORTED = "imported"
    SKIPPED = "skipped"  # already up to date, no write needed
    MISSING_PRODUCT = "missing_product"
    CONTENT_HASH_MISMATCH = "content_hash_mismatch"
    INVALID_EMBEDDING = "invalid_embedding"
    FAILURE = "failure"


@dataclass
class LocalProductRecord:
    """The subset of current local DB state needed to validate one import row."""
    id: str
    content_hash: Optional[str]
    embedding_content_hash: Optional[str]


@dataclass
class ArtifactRow:
    """One row read back from the Colab-produced result Parquet."""
    id: str
    external_product_id: str
    content_hash: str
    embedding: List[float]


@dataclass
class ImportDecision:
    """What to do with one artifact row, and why."""
    outcome: ImportOutcome
    external_product_id: str
    reason: str = ""
    # Only populated when outcome == IMPORTED.
    update_payload: Optional[dict] = None


EXPECTED_DIM = 768


def classify_row(
    row: ArtifactRow,
    local_products_by_external_id: Dict[str, LocalProductRecord],
) -> ImportDecision:
    """Decide what to do with one artifact row against current local DB state.

    Validation order matters: identity (does this row even refer to a real,
    matching product) is checked before content (is the embedding itself
    well-formed) before staleness (has the product changed since export) -
    so a row that fails for multiple reasons is reported under the most
    fundamental cause.
    """
    local = local_products_by_external_id.get(row.external_product_id)

    if local is None:
        return ImportDecision(
            ImportOutcome.MISSING_PRODUCT,
            row.external_product_id,
            reason=f"no product with external_product_id={row.external_product_id!r}",
        )

    # Data-integrity cross-check: the artifact's own id column (if present)
    # must agree with the product resolved by external_product_id. A
    # mismatch means the artifact is corrupt or was mis-joined upstream -
    # refuse to write rather than risk attaching an embedding to the wrong
    # product.
    if row.id and row.id != local.id:
        return ImportDecision(
            ImportOutcome.FAILURE,
            row.external_product_id,
            reason=(
                f"identity mismatch: artifact id={row.id!r} does not match "
                f"local product id={local.id!r} for external_product_id="
                f"{row.external_product_id!r}"
            ),
        )

    if not _is_valid_embedding(row.embedding):
        return ImportDecision(
            ImportOutcome.INVALID_EMBEDDING,
            row.external_product_id,
            reason=f"embedding has {_embedding_len(row.embedding)} dims (expected {EXPECTED_DIM}) or non-finite values",
        )

    if row.content_hash != local.content_hash:
        return ImportDecision(
            ImportOutcome.CONTENT_HASH_MISMATCH,
            row.external_product_id,
            reason=(
                f"artifact content_hash={row.content_hash!r} does not match "
                f"current product content_hash={local.content_hash!r} "
                "(product changed locally since export; skipping to avoid "
                "writing a stale embedding)"
            ),
        )

    if local.embedding_content_hash == row.content_hash:
        return ImportDecision(
            ImportOutcome.SKIPPED,
            row.external_product_id,
            reason="already up to date (embedding_content_hash already matches content_hash)",
        )

    return ImportDecision(
        ImportOutcome.IMPORTED,
        row.external_product_id,
        update_payload={
            "id": local.id,
            "embedding": list(row.embedding),
            "embedding_content_hash": row.content_hash,
        },
    )


def _embedding_len(embedding) -> int:
    try:
        return len(embedding)
    except TypeError:
        return -1


def _is_valid_embedding(embedding) -> bool:
    if embedding is None:
        return False
    try:
        values = list(embedding)
    except TypeError:
        return False
    if len(values) != EXPECTED_DIM:
        return False
    for v in values:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return False
        if fv != fv or fv in (float("inf"), float("-inf")):  # NaN/Inf check
            return False
    return True
