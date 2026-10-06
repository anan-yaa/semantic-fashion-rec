"""Unit tests for ingestion service orchestration."""

from typing import ClassVar

from app.db.repositories.product_repository import ProductRepository
from app.services.ingestion.service import (
    IngestionStats,
    ingest_records,
)


class TestIngestionStats:
    """Test statistics tracking."""

    def test_initialization(self):
        stats = IngestionStats()
        assert stats.inserted == 0
        assert stats.updated == 0
        assert stats.skipped == 0
        assert stats.invalid == 0

    def test_repr(self):
        stats = IngestionStats()
        stats.inserted = 5
        stats.updated = 2
        stats.skipped = 1
        stats.invalid = 0
        repr_str = repr(stats)
        assert "inserted=5" in repr_str
        assert "updated=2" in repr_str
        assert "skipped=1" in repr_str
        assert "invalid=0" in repr_str


class TestIngestRecords:
    """Test ingestion service."""

    def test_ingest_new_products(self, repository: ProductRepository, test_db):
        """New products are inserted."""
        records = [
            {
                "id": 1001,
                "productDisplayName": "Shirt",
                "gender": "Men",
                "masterCategory": "Apparel",
            },
            {
                "id": 1002,
                "productDisplayName": "Jeans",
                "gender": "Women",
                "masterCategory": "Apparel",
            },
        ]

        stats = ingest_records(test_db, records)
        assert stats.inserted == 2
        assert stats.updated == 0
        assert stats.skipped == 0
        assert stats.invalid == 0

        # Verify in database
        p1 = repository.get_by_external_id("1001")
        p2 = repository.get_by_external_id("1002")
        assert p1 is not None
        assert p2 is not None
        assert p1.name == "Shirt"
        assert p2.name == "Jeans"

    def test_ingest_unchanged_products_skipped(self, repository: ProductRepository, test_db):
        """Same product ingested twice is skipped on second run."""
        record_dict = {
            "id": 2001,
            "productDisplayName": "Test Shirt",
            "gender": "Men",
            "masterCategory": "Apparel",
        }

        # First ingestion
        stats1 = ingest_records(test_db, [record_dict])
        assert stats1.inserted == 1
        assert stats1.skipped == 0

        # Second ingestion - same data
        stats2 = ingest_records(test_db, [record_dict])
        assert stats2.inserted == 0
        assert stats2.skipped == 1

    def test_ingest_changed_products_updated(self, repository: ProductRepository, test_db):
        """Changed product is updated."""
        record1 = {
            "id": 3001,
            "productDisplayName": "Original Shirt",
            "gender": "Men",
            "masterCategory": "Apparel",
        }

        # First ingestion
        stats1 = ingest_records(test_db, [record1])
        assert stats1.inserted == 1

        p1 = repository.get_by_external_id("3001")
        original_hash = p1.content_hash

        # Changed product
        record2 = {
            "id": 3001,
            "productDisplayName": "Updated Shirt",
            "gender": "Women",
            "masterCategory": "Apparel",
        }

        # Second ingestion - different data
        stats2 = ingest_records(test_db, [record2])
        assert stats2.inserted == 0
        assert stats2.updated == 1

        # Verify update
        p2 = repository.get_by_external_id("3001")
        assert p2.name == "Updated Shirt"
        assert p2.gender == "Women"
        assert p2.content_hash != original_hash

    def test_ingest_invalid_records(self, test_db):
        """Invalid records are skipped and counted."""
        records = [
            {
                "id": 4001,
                "productDisplayName": "Valid",
                "gender": "Men",
            },
            {
                # Missing productDisplayName
                "id": 4002,
                "gender": "Men",
            },
            {
                # Invalid type for id
                "id": "invalid",
                "productDisplayName": "Another",
            },
        ]

        stats = ingest_records(test_db, records)
        assert stats.inserted == 1
        assert stats.invalid == 2

    def test_ingest_duplicate_ids_in_batch(self, test_db):
        """Duplicate IDs in batch are detected."""
        records = [
            {
                "id": 5001,
                "productDisplayName": "First",
                "gender": "Men",
            },
            {
                "id": 5001,  # Duplicate
                "productDisplayName": "Second",
                "gender": "Women",
            },
        ]

        stats = ingest_records(test_db, records)
        # First one inserted, second is duplicate and invalid
        assert stats.inserted == 1
        assert stats.invalid == 1

    def test_ingest_batch_size(self, repository: ProductRepository, test_db):
        """Batch size is respected."""
        records = []
        for i in range(25):
            records.append({
                "id": 6000 + i,
                "productDisplayName": f"Product {i}",
                "gender": "Men",
            })

        stats = ingest_records(test_db, records, batch_size=10)
        assert stats.inserted == 25

        # Verify all are in database
        for i in range(25):
            p = repository.get_by_external_id(str(6000 + i))
            assert p is not None

    def test_ingest_statistics_totals(self, test_db):
        """Statistics add up correctly."""
        records = [
            {"id": 7001, "productDisplayName": "Valid 1"},
            {"id": 7002, "productDisplayName": "Valid 2"},
            {"id": 7003},  # Invalid
            {"id": "invalid", "productDisplayName": "Also invalid"},
        ]

        stats = ingest_records(test_db, records)
        total = stats.inserted + stats.updated + stats.skipped + stats.invalid
        assert total == 4


class TestCatalogueAvailabilitySync:
    """Products leaving and re-entering the feed."""

    FEED: ClassVar[list[dict]] = [
        {"id": 8001, "productDisplayName": "Shirt", "gender": "Men"},
        {"id": 8002, "productDisplayName": "Dress", "gender": "Women"},
        {"id": 8003, "productDisplayName": "Belt", "gender": "Men"},
    ]

    def test_missing_products_marked_unavailable(self, repository: ProductRepository, test_db):
        ingest_records(test_db, self.FEED)

        stats = ingest_records(test_db, self.FEED[:2], mark_missing_unavailable=True)

        assert stats.deactivated == 1
        assert stats.skipped == 2
        test_db.expire_all()
        assert repository.get_by_external_id("8003").availability is False
        assert repository.get_by_external_id("8001").availability is True

    def test_missing_products_kept_without_flag(self, repository: ProductRepository, test_db):
        ingest_records(test_db, self.FEED)

        stats = ingest_records(test_db, self.FEED[:2])

        assert stats.deactivated == 0
        assert repository.get_by_external_id("8003").availability is True

    def test_returning_product_reactivated(self, repository: ProductRepository, test_db):
        ingest_records(test_db, self.FEED)
        ingest_records(test_db, self.FEED[:2], mark_missing_unavailable=True)

        stats = ingest_records(test_db, self.FEED, mark_missing_unavailable=True)

        assert stats.reactivated == 1
        assert stats.deactivated == 0
        test_db.expire_all()
        assert repository.get_by_external_id("8003").availability is True

    def test_returning_changed_product_reactivated_and_updated(self, repository: ProductRepository, test_db):
        ingest_records(test_db, self.FEED)
        ingest_records(test_db, self.FEED[:2], mark_missing_unavailable=True)
        changed = {"id": 8003, "productDisplayName": "Leather Belt", "gender": "Men"}

        stats = ingest_records(test_db, [*self.FEED[:2], changed], mark_missing_unavailable=True)

        assert stats.updated == 1
        assert stats.reactivated == 1
        test_db.expire_all()
        product = repository.get_by_external_id("8003")
        assert product.availability is True
        assert product.name == "Leather Belt"

    def test_empty_feed_does_not_deactivate_catalogue(self, repository: ProductRepository, test_db):
        ingest_records(test_db, self.FEED)

        stats = ingest_records(test_db, [], mark_missing_unavailable=True)

        assert stats.deactivated == 0
        assert repository.get_by_external_id("8001").availability is True
