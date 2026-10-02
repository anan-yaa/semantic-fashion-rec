"""Integration tests for PostgreSQL full-text keyword search (ts_rank, plainto_tsquery)."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.services.keyword_index import build_keyword_index
from app.services.search.keyword_search import search_keyword
from app.schemas.search import SearchFilter


def make_product(pid: str, name: str, search_text: str, **kwargs) -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        search_text=search_text,
        content_hash=f"hash_{pid}",
        **kwargs,
    )


class TestKeywordSearchPostgresIntegration:
    """Test suite for PostgreSQL TSVECTOR full-text search (not the ILIKE fallback)."""

    def test_search_uses_tsvector_match(self, postgres_session: Session):
        """Test that search matches against the indexed search_vector, not ILIKE."""
        p = make_product("p1", "Blue Cotton Shirt", "blue cotton shirt for men")
        postgres_session.add(p)
        postgres_session.commit()

        # Index first (search_vector must be populated for FTS to find it)
        build_keyword_index(postgres_session, limit=100)

        results, total = search_keyword(postgres_session, "cotton", limit=10)

        assert total == 1
        assert results[0].id == "p1"

    def test_unindexed_product_not_found_by_fts(self, postgres_session: Session):
        """Test that a product without a built search_vector isn't matched by FTS
        (confirms we're using the real tsvector column, not falling back silently)."""
        p = make_product("p1", "Blue Cotton Shirt", "blue cotton shirt")
        postgres_session.add(p)
        postgres_session.commit()
        # Deliberately do NOT call build_keyword_index

        results, total = search_keyword(postgres_session, "cotton", limit=10)

        assert total == 0

    def test_stemming_matches_related_words(self, postgres_session: Session):
        """Test that PostgreSQL's English stemming matches word variants (e.g. 'shirts' -> 'shirt')."""
        p = make_product("p1", "Running Shoes", "running shoes for athletes")
        postgres_session.add(p)
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        # 'run' should match 'running' via English stemming
        results, total = search_keyword(postgres_session, "run", limit=10)

        assert total == 1

    def test_relevance_ranking_with_ts_rank(self, postgres_session: Session):
        """Test that results are ranked by relevance (ts_rank_cd), most relevant first."""
        # p1 mentions "shirt" once, p2 mentions it multiple times (higher density -> higher rank)
        p1 = make_product("p1", "Item", "a blue shirt for casual wear")
        p2 = make_product("p2", "Shirt Shirt Shirt", "shirt shirt shirt shirt")
        postgres_session.add_all([p1, p2])
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        results, total = search_keyword(postgres_session, "shirt", limit=10)

        assert total == 2
        # p2 has higher term frequency, should rank first under ts_rank_cd
        assert results[0].id == "p2"

    def test_no_match_returns_empty(self, postgres_session: Session):
        """Test that unrelated query terms return no results."""
        p = make_product("p1", "Blue Shirt", "blue cotton shirt")
        postgres_session.add(p)
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        results, total = search_keyword(postgres_session, "spaceship", limit=10)

        assert total == 0

    def test_search_with_filters(self, postgres_session: Session):
        """Test FTS search respects filters alongside tsquery matching."""
        p1 = make_product("p1", "Blue Shirt", "blue shirt", gender="Men")
        p2 = make_product("p2", "Blue Shirt", "blue shirt", gender="Women")
        postgres_session.add_all([p1, p2])
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        filters = SearchFilter(gender="Women")
        results, total = search_keyword(postgres_session, "blue", filters=filters, limit=10)

        assert total == 1
        assert results[0].gender == "Women"

    def test_gin_index_is_used(self, postgres_session: Session):
        """Verify the query planner uses the GIN index for tsvector matching."""
        for i in range(5):
            p = make_product(f"p{i}", f"Product {i}", f"searchable text number {i}")
            postgres_session.add(p)
        postgres_session.commit()

        build_keyword_index(postgres_session, limit=100)

        postgres_session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = postgres_session.execute(text(
            "EXPLAIN SELECT id FROM products WHERE search_vector @@ plainto_tsquery('english', 'searchable')"
        )).fetchall()

        plan_text = "\n".join(row[0] for row in plan)
        assert "idx_search_vector_gin" in plan_text
