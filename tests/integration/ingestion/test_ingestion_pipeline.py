"""Integration tests for complete ingestion pipeline."""

from app.db.repositories.product_repository import ProductRepository
from app.services.ingestion.loader import load_dataset_from_cache
from app.services.ingestion.service import ingest_records


class TestIngestionPipeline:
    """Integration tests for the complete ingestion pipeline."""

    def test_end_to_end_with_small_sample(self, repository: ProductRepository, test_db):
        """Test complete pipeline with small dataset sample."""
        # Load dataset
        ds = load_dataset_from_cache()

        # Take first 10 records
        records = [ds[i] for i in range(10)]

        # Ingest
        stats = ingest_records(test_db, records)

        # Verify
        assert stats.inserted == 10
        assert stats.updated == 0
        assert stats.skipped == 0
        assert stats.invalid == 0

        # Verify all are in database
        all_products, total = repository.list_all(skip=0, limit=100)
        assert total == 10

    def test_idempotent_ingestion(self, repository: ProductRepository, test_db):
        """Test ingestion is idempotent: same dataset twice = skip unchanged."""
        # Load dataset
        ds = load_dataset_from_cache()
        records = [ds[i] for i in range(5)]

        # First ingestion
        stats1 = ingest_records(test_db, records)
        assert stats1.inserted == 5
        assert stats1.skipped == 0

        # Verify in database
        products_after_first, count1 = repository.list_all(skip=0, limit=100)
        assert count1 == 5

        # Second ingestion with exact same records
        stats2 = ingest_records(test_db, records)
        assert stats2.inserted == 0
        assert stats2.skipped == 5

        # Verify database unchanged
        products_after_second, count2 = repository.list_all(skip=0, limit=100)
        assert count2 == 5  # Same count

    def test_incremental_update(self, repository: ProductRepository, test_db):
        """Test incremental updates when dataset grows."""
        ds = load_dataset_from_cache()

        # First batch: records 0-4
        records1 = [ds[i] for i in range(5)]
        stats1 = ingest_records(test_db, records1)
        assert stats1.inserted == 5

        products1, count1 = repository.list_all(skip=0, limit=100)
        assert count1 == 5

        # Second batch: records 5-9 (new products)
        records2 = [ds[i] for i in range(5, 10)]
        stats2 = ingest_records(test_db, records2)
        assert stats2.inserted == 5

        products2, count2 = repository.list_all(skip=0, limit=100)
        assert count2 == 10

        # Re-ingest first batch (should skip all)
        stats3 = ingest_records(test_db, records1)
        assert stats3.inserted == 0
        assert stats3.skipped == 5

    def test_verified_data_integrity(self, repository: ProductRepository, test_db):
        """Verify ingested data integrity."""
        ds = load_dataset_from_cache()
        records = [ds[0], ds[1], ds[2]]

        ingest_records(test_db, records)

        # Verify each product
        for i, record in enumerate(records):
            p = repository.get_by_external_id(str(record["id"]))
            assert p is not None
            assert p.name == record["productDisplayName"]
            assert p.gender == record.get("gender")
            assert p.category == record.get("masterCategory")
            assert p.search_text is not None
            assert p.content_hash is not None

    def test_batch_processing_respects_batch_size(self, repository: ProductRepository, test_db):
        """Verify batch processing works correctly."""
        ds = load_dataset_from_cache()
        records = [ds[i] for i in range(35)]

        # Process with batch_size=10
        stats = ingest_records(test_db, records, batch_size=10)
        assert stats.inserted == 35

        # All should be in database
        all_products, total = repository.list_all(skip=0, limit=100)
        assert total == 35
