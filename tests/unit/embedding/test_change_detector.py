"""Tests for change detection in embedding service."""
import pytest
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.embedding.change_detector import get_products_needing_embedding, count_products_needing_embedding


class TestChangeDetector:
    """Test suite for change detection."""

    def test_get_unembedded_products(self, test_db: Session):
        """Test finding products with no embedding."""
        # Create product without embedding
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Test",
            search_text="test shirt",
            content_hash="hash1",
            embedding=None,
            embedding_content_hash=None,
        )
        test_db.add(p)
        test_db.commit()

        products = get_products_needing_embedding(test_db, limit=10)

        assert len(products) == 1
        assert products[0].id == "p1"

    def test_get_changed_products(self, test_db: Session):
        """Test finding products whose content changed since embedding."""
        # Create product that was embedded but changed
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Test",
            search_text="test shirt",
            content_hash="hash2",  # Current hash
            embedding=[0.1] * 768,
            embedding_content_hash="hash1",  # Old hash - content changed!
        )
        test_db.add(p)
        test_db.commit()

        products = get_products_needing_embedding(test_db, limit=10)

        assert len(products) == 1
        assert products[0].id == "p1"

    def test_skip_unchanged_products(self, test_db: Session):
        """Test that unchanged embedded products are skipped."""
        # Create product that's been embedded and hasn't changed
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Test",
            search_text="test shirt",
            content_hash="hash1",
            embedding=[0.1] * 768,
            embedding_content_hash="hash1",  # Matches content_hash
        )
        test_db.add(p)
        test_db.commit()

        products = get_products_needing_embedding(test_db, limit=10)

        assert len(products) == 0

    def test_count_needing_embedding(self, test_db: Session):
        """Test counting products needing embedding."""
        # Add 3 products: 2 need embedding, 1 doesn't
        for i in range(2):
            p = Product(
                id=f"p{i}",
                external_product_id=f"ext{i}",
                name=f"Test {i}",
                search_text=f"test {i}",
                content_hash=f"hash{i}",
                embedding=None,
            )
            test_db.add(p)

        p = Product(
            id="p2",
            external_product_id="ext2",
            name="Test 2",
            search_text="test 2",
            content_hash="hash2",
            embedding=[0.1] * 768,
            embedding_content_hash="hash2",
        )
        test_db.add(p)
        test_db.commit()

        count = count_products_needing_embedding(test_db)

        assert count == 2
