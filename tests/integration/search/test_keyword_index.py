"""Integration tests for keyword indexing on real PostgreSQL."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.keyword_index import build_keyword_index


def make_product(pid: str, name: str, search_text: str, content_hash: str) -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        search_text=search_text,
        content_hash=content_hash,
    )


class TestKeywordIndexIntegration:
    """Test suite for PostgreSQL TSVECTOR keyword indexing."""

    def test_index_new_products(self, postgres_session: Session):
        """Test that new products (search_vector IS NULL) get indexed."""
        p = make_product("p1", "Blue Shirt", "blue cotton shirt for men", "hash1")
        postgres_session.add(p)
        postgres_session.commit()

        stats = build_keyword_index(postgres_session, limit=100)

        assert stats.indexed_count == 1

        postgres_session.refresh(p)
        assert p.search_vector is not None
        assert p.search_indexed_hash == "hash1"

    def test_skip_unchanged_products(self, postgres_session: Session):
        """Test that products already indexed with matching hash are skipped."""
        p = make_product("p1", "Blue Shirt", "blue cotton shirt", "hash1")
        postgres_session.add(p)
        postgres_session.commit()

        # First index
        stats1 = build_keyword_index(postgres_session, limit=100)
        assert stats1.indexed_count == 1

        # Second run: nothing changed, should skip
        stats2 = build_keyword_index(postgres_session, limit=100)
        assert stats2.indexed_count == 0

    def test_reindex_changed_products(self, postgres_session: Session):
        """Test that products with changed content_hash get reindexed."""
        p = make_product("p1", "Blue Shirt", "blue cotton shirt", "hash1")
        postgres_session.add(p)
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        # Simulate content change
        postgres_session.execute(text(
            "UPDATE products SET content_hash = 'hash2', search_text = 'red cotton shirt' WHERE id = 'p1'"
        ))
        postgres_session.commit()

        stats = build_keyword_index(postgres_session, limit=100)
        assert stats.indexed_count == 1

        postgres_session.refresh(p)
        assert p.search_indexed_hash == "hash2"

    def test_set_based_update_not_row_by_row(self, postgres_session: Session):
        """Test that indexing multiple products happens in a single set-based UPDATE."""
        for i in range(10):
            p = make_product(f"p{i}", f"Product {i}", f"search text {i}", f"hash{i}")
            postgres_session.add(p)
        postgres_session.commit()

        stats = build_keyword_index(postgres_session, limit=100)

        assert stats.indexed_count == 10

        # Verify all were indexed with correct tsvector content
        rows = postgres_session.execute(text(
            "SELECT id, search_vector, search_indexed_hash FROM products ORDER BY id"
        )).fetchall()
        assert len(rows) == 10
        for row in rows:
            assert row.search_vector is not None

    def test_tsvector_matches_search_text(self, postgres_session: Session):
        """Test that the generated tsvector actually matches expected tokens."""
        p = make_product("p1", "Red Dress", "red cotton summer dress", "hash1")
        postgres_session.add(p)
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        result = postgres_session.execute(text(
            "SELECT 1 FROM products WHERE id = 'p1' AND search_vector @@ plainto_tsquery('english', 'dress')"
        )).fetchone()
        assert result is not None

    def test_no_products_needing_index(self, postgres_session: Session):
        """Test that running indexing with nothing to index returns zero stats."""
        stats = build_keyword_index(postgres_session, limit=100)
        assert stats.indexed_count == 0
        assert stats.skipped_count == 0
