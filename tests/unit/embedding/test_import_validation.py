"""Tests for the embedding-import data-integrity/validation logic.

This is the part of the Colab import workflow that matters most: it must
never associate an embedding with the wrong product, and must never
overwrite an embedding with stale data.
"""
from app.services.embedding.import_validation import (
    ArtifactRow,
    ImportOutcome,
    LocalProductRecord,
    classify_row,
)

GOOD_EMBEDDING = [0.1] * 768


def make_row(**overrides) -> ArtifactRow:
    defaults = dict(
        id="p1",
        external_product_id="ext1",
        content_hash="hash_v1",
        embedding=GOOD_EMBEDDING,
    )
    defaults.update(overrides)
    return ArtifactRow(**defaults)


def make_local(**overrides) -> LocalProductRecord:
    defaults = dict(id="p1", content_hash="hash_v1", embedding_content_hash=None)
    defaults.update(overrides)
    return LocalProductRecord(**defaults)


class TestClassifyRow:
    def test_missing_product_is_reported(self):
        decision = classify_row(make_row(external_product_id="ghost"), {})
        assert decision.outcome == ImportOutcome.MISSING_PRODUCT

    def test_stale_artifact_id_does_not_block_import(self):
        """The artifact's id column is not a match/integrity key - it's a
        randomly generated surrogate key (uuid.uuid4()) that gets
        regenerated on every re-ingestion, so a stale id from before a
        catalogue reload must not block an otherwise-valid import.
        external_product_id (the match key) + content_hash (the content
        proof) are what guarantee correct association; the write must
        always target the CURRENT local.id, never the artifact's stale id.
        """
        local = {"ext1": make_local(id="CURRENT_PRODUCT_ID")}
        row = make_row(external_product_id="ext1", id="STALE_ID_FROM_BEFORE_RELOAD")

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.IMPORTED
        assert decision.update_payload["id"] == "CURRENT_PRODUCT_ID"

    def test_wrong_dimension_embedding_is_invalid(self):
        local = {"ext1": make_local()}
        row = make_row(embedding=[0.1] * 100)

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.INVALID_EMBEDDING

    def test_nan_in_embedding_is_invalid(self):
        local = {"ext1": make_local()}
        bad = [0.1] * 767 + [float("nan")]
        row = make_row(embedding=bad)

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.INVALID_EMBEDDING

    def test_content_hash_mismatch_is_not_overwritten(self):
        """If the product changed locally since export, the row must be
        skipped - never blindly overwritten with a stale embedding."""
        local = {"ext1": make_local(content_hash="hash_v2_changed_locally")}
        row = make_row(content_hash="hash_v1")

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.CONTENT_HASH_MISMATCH
        assert decision.update_payload is None

    def test_already_up_to_date_is_skipped_not_rewritten(self):
        local = {"ext1": make_local(content_hash="hash_v1", embedding_content_hash="hash_v1")}
        row = make_row(content_hash="hash_v1")

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.SKIPPED
        assert decision.update_payload is None

    def test_valid_new_embedding_is_imported(self):
        local = {"ext1": make_local(content_hash="hash_v1", embedding_content_hash=None)}
        row = make_row(content_hash="hash_v1")

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.IMPORTED
        assert decision.update_payload["id"] == "p1"
        assert decision.update_payload["embedding"] == GOOD_EMBEDDING
        assert decision.update_payload["embedding_content_hash"] == "hash_v1"

    def test_valid_changed_embedding_is_reimported(self):
        """A product whose content_hash advanced (and was re-embedded) must
        be imported even though it already has some embedding_content_hash,
        as long as the artifact's hash matches the NEW current hash."""
        local = {"ext1": make_local(content_hash="hash_v2", embedding_content_hash="hash_v1")}
        row = make_row(content_hash="hash_v2")

        decision = classify_row(row, local)

        assert decision.outcome == ImportOutcome.IMPORTED

    def test_second_import_of_same_artifact_is_idempotent(self):
        """Applying the same artifact row twice: first import writes,
        second import is a no-op skip - not a duplicate write or an error."""
        local = {"ext1": make_local(content_hash="hash_v1", embedding_content_hash=None)}
        row = make_row(content_hash="hash_v1")

        first = classify_row(row, local)
        assert first.outcome == ImportOutcome.IMPORTED

        # Simulate the write having been applied.
        local["ext1"].embedding_content_hash = first.update_payload["embedding_content_hash"]

        second = classify_row(row, local)
        assert second.outcome == ImportOutcome.SKIPPED
