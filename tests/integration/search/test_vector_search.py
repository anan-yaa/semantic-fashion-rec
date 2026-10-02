"""Integration tests for vector similarity search on real pgvector."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.services.search.vector_search import search_vector
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


class TestVectorSearchIntegration:
    """Test suite for pgvector-backed vector search."""

    def test_search_returns_embedded_products(self, postgres_session: Session):
        """Test that vector search returns products with embeddings."""
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Blue Shirt", "blue cotton shirt")
        p1.embedding = provider.embed_passages(["blue cotton shirt"])[0]
        postgres_session.add(p1)
        postgres_session.commit()

        results, total = search_vector(postgres_session, "blue shirt", provider, limit=10)

        assert total == 1
        assert len(results) == 1
        assert results[0].id == "p1"

    def test_excludes_unembedded_products(self, postgres_session: Session):
        """Test that products without embeddings are excluded from vector search."""
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Blue Shirt", "blue shirt")
        p1.embedding = provider.embed_passages(["blue shirt"])[0]
        p2 = make_product("p2", "Red Shirt", "red shirt")  # No embedding

        postgres_session.add_all([p1, p2])
        postgres_session.commit()

        results, total = search_vector(postgres_session, "shirt", provider, limit=10)

        assert total == 1
        assert results[0].id == "p1"

    def test_most_similar_ranked_first(self, postgres_session: Session):
        """Test that the closer embedding (by deterministic fake hash) ranks higher."""
        provider = FakeEmbeddingProvider()

        # Same text as query -> identical embedding -> distance 0 (most similar)
        exact_match = make_product("exact", "blue cotton shirt", "blue cotton shirt")
        exact_match.embedding = provider.embed_passages(["blue cotton shirt"])[0]

        different = make_product("different", "winter wool coat", "winter wool coat")
        different.embedding = provider.embed_passages(["winter wool coat"])[0]

        postgres_session.add_all([exact_match, different])
        postgres_session.commit()

        # Query embedding matches 'exact' product's passage embedding exactly
        # (FakeEmbeddingProvider is deterministic on text content)
        results, _ = search_vector(postgres_session, "blue cotton shirt", provider, limit=10)

        assert len(results) == 2
        assert results[0].id == "exact"

    def test_search_with_filters(self, postgres_session: Session):
        """Test vector search respects filters."""
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Shirt", "shirt", gender="Men")
        p1.embedding = provider.embed_passages(["shirt"])[0]
        p2 = make_product("p2", "Shirt", "shirt", gender="Women")
        p2.embedding = provider.embed_passages(["shirt"])[0]

        postgres_session.add_all([p1, p2])
        postgres_session.commit()

        filters = SearchFilter(gender="Men")
        results, total = search_vector(postgres_session, "shirt", provider, filters=filters, limit=10)

        assert total == 1
        assert results[0].gender == "Men"

    def test_hnsw_index_is_used(self, postgres_session: Session):
        """Verify the query planner can use the HNSW index for cosine distance ordering.

        Uses `SET enable_seqscan = off` to force index selection, which avoids
        flakiness from the planner preferring a sequential scan on a tiny
        test dataset.
        """
        provider = FakeEmbeddingProvider()
        for i in range(5):
            p = make_product(f"p{i}", f"Product {i}", f"text {i}")
            p.embedding = provider.embed_passages([f"text {i}"])[0]
            postgres_session.add(p)
        postgres_session.commit()

        query_embedding = provider.embed_queries(["text 0"])[0]

        postgres_session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = postgres_session.execute(text(
            "EXPLAIN SELECT id FROM products WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> (:qvec)::vector LIMIT 5"
        ), {"qvec": str(query_embedding)}).fetchall()

        plan_text = "\n".join(row[0] for row in plan)
        assert "idx_embedding_hnsw" in plan_text
