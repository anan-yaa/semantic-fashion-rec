"""Integration tests for build_pool() against real PostgreSQL.

Uses FakeEmbeddingProvider (never the real E5 model), following the same
pattern as tests/integration/search/test_hybrid_search.py: "a strong vector
match" is modeled as "embedded with the exact query text" (guaranteed
distance 0), since FakeEmbeddingProvider has no real notion of semantic
similarity.
"""
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.services.eval import QuerySetEntry, build_pool, load_pool, save_pool
from app.services.keyword_index import build_keyword_index

QUERY = "distinctive zephyr product"


def make_product(pid: str, name: str, search_text: str, **kwargs) -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        search_text=search_text,
        content_hash=f"hash_{pid}",
        **kwargs,
    )


class TestBuildPoolIntegration:
    def test_every_retrieved_product_appears_exactly_once(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        keyword_hit = make_product("keyword_hit", "Keyword Only", "zephyr accessory")
        keyword_hit.embedding = provider.embed_passages(["unrelated content xyz"])[0]

        vector_hit = make_product("vector_hit", "Vector Only", "completely unrelated wording")
        vector_hit.embedding = provider.embed_passages([QUERY])[0]

        both_hit = make_product("both_hit", "Both", QUERY)
        both_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add_all([keyword_hit, vector_hit, both_hit])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        queries = [QuerySetEntry(id="q1", query=QUERY, category_tag="test")]
        pools, stats = build_pool(postgres_session, provider, queries, k_per_method=10)

        assert len(pools) == 1
        candidate_ids = [c.product_id for c in pools[0].candidates]
        assert sorted(candidate_ids) == sorted(set(candidate_ids))  # no duplicates
        assert set(candidate_ids) == {"keyword_hit", "vector_hit", "both_hit"}
        assert stats.query_count == 1

    def test_found_by_correctly_attributes_each_method(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        # plainto_tsquery ANDs all terms, so search_text must contain every
        # query token to match - "zephyr" alone is not enough. No embedding
        # is set, so vector search (which filters to non-null embeddings)
        # structurally cannot return this product - the only reliable way
        # to exclude something from vector's results, since vector search
        # itself has no relevance threshold (any embedded product appears
        # regardless of rank, confirmed in test_hybrid_search.py).
        keyword_hit = make_product("keyword_hit", "Keyword Only", QUERY)

        vector_hit = make_product("vector_hit", "Vector Only", "completely unrelated wording")
        vector_hit.embedding = provider.embed_passages([QUERY])[0]

        both_hit = make_product("both_hit", "Both", QUERY)
        both_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add_all([keyword_hit, vector_hit, both_hit])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        queries = [QuerySetEntry(id="q1", query=QUERY, category_tag="test")]
        pools, _ = build_pool(postgres_session, provider, queries, k_per_method=10)

        by_id = {c.product_id: c for c in pools[0].candidates}
        assert "keyword" in by_id["keyword_hit"].found_by
        assert "vector" not in by_id["keyword_hit"].found_by

        assert "vector" in by_id["vector_hit"].found_by
        assert "keyword" not in by_id["vector_hit"].found_by

        assert "vector" in by_id["both_hit"].found_by
        assert "keyword" in by_id["both_hit"].found_by
        assert "hybrid" in by_id["both_hit"].found_by

    def test_pool_round_trips_through_json(self, postgres_session: Session, tmp_path):
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        queries = [QuerySetEntry(id="q1", query=QUERY, category_tag="test")]
        pools, _ = build_pool(postgres_session, provider, queries, k_per_method=10)

        path = str(tmp_path / "pool.json")
        save_pool(path, pools, source_query_set="test.json", k_per_method=10, built_at="2026-01-01T00:00:00Z")
        loaded = load_pool(path)

        assert len(loaded) == 1
        assert loaded[0].query_id == "q1"
        assert {c.product_id for c in loaded[0].candidates} == {"p1"}
        assert loaded[0].candidates[0].pre_label is None
