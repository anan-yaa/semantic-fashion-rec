"""Tests for keyword search."""
import pytest
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.search.keyword_search import search_keyword
from app.schemas.search import SearchFilter


class TestKeywordSearch:
    """Test suite for keyword search."""

    def test_search_by_name(self, test_db: Session):
        """Test finding products by name."""
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Blue Cotton Shirt",
            search_text="blue cotton shirt",
            content_hash="hash1",
        )
        test_db.add(p)
        test_db.commit()

        results, total = search_keyword(test_db, "blue", limit=10)

        assert len(results) == 1
        assert results[0].id == "p1"
        assert total == 1

    def test_search_multiple_tokens(self, test_db: Session):
        """Test searching with multiple tokens."""
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Blue Cotton Shirt",
            search_text="blue cotton shirt",
            content_hash="hash1",
        )
        test_db.add(p)
        test_db.commit()

        results, total = search_keyword(test_db, "cotton shirt", limit=10)

        assert len(results) == 1

    def test_search_no_results(self, test_db: Session):
        """Test search with no matching products."""
        p = Product(
            id="p1",
            external_product_id="ext1",
            name="Blue Shirt",
            search_text="blue shirt",
            content_hash="hash1",
        )
        test_db.add(p)
        test_db.commit()

        results, total = search_keyword(test_db, "red", limit=10)

        assert len(results) == 0
        assert total == 0

    def test_search_with_filter(self, test_db: Session):
        """Test search with filters."""
        # Add 2 products
        for i, gender in enumerate(["Men", "Women"]):
            p = Product(
                id=f"p{i}",
                external_product_id=f"ext{i}",
                name="Blue Shirt",
                gender=gender,
                search_text="blue shirt",
                content_hash=f"hash{i}",
            )
            test_db.add(p)
        test_db.commit()

        # Search for men only
        filters = SearchFilter(gender="Men")
        results, total = search_keyword(test_db, "blue", filters=filters, limit=10)

        assert len(results) == 1
        assert results[0].gender == "Men"

    def test_search_limit(self, test_db: Session):
        """Test that limit is respected."""
        # Add 5 products
        for i in range(5):
            p = Product(
                id=f"p{i}",
                external_product_id=f"ext{i}",
                name=f"Shirt {i}",
                search_text="shirt",
                content_hash=f"hash{i}",
            )
            test_db.add(p)
        test_db.commit()

        results, total = search_keyword(test_db, "shirt", limit=3)

        assert len(results) == 3
        assert total == 5
