"""Integration tests for hybrid search (vector + keyword via RRF) on real PostgreSQL.

FakeEmbeddingProvider is deterministic by exact text (identical text produces
an identical vector, i.e. cosine distance 0) but otherwise produces
effectively random, unrelated vectors for different strings -- it has no
notion of semantic similarity. So throughout these tests, "a strong vector
match" is modeled as "embedded with the exact query text" (guaranteed
distance 0, i.e. guaranteed top rank via vector search), not textual
similarity. Vector search itself has no relevance threshold, so every
embedded product appears in its result set, just ranked by distance.
"""
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.schemas.search import SearchFilter, SearchMethod
from app.services.keyword_index import build_keyword_index
from app.services.search.hybrid import search_hybrid

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


class TestHybridSearchIntegration:
    """Test suite for hybrid search combining vector + keyword via RRF."""

    def test_hybrid_combines_vector_and_keyword_results(self, postgres_session: Session):
        """Test that hybrid search surfaces results found by either method."""
        provider = FakeEmbeddingProvider()

        # Keyword-findable only: shares a query token, embedding is unrelated.
        keyword_hit = make_product("keyword_hit", "Keyword Only", "zephyr accessory")
        keyword_hit.embedding = provider.embed_passages(["unrelated content xyz"])[0]

        # Vector-findable only: embedding is an exact match to the query text
        # (guaranteed distance 0), search_text shares no tokens with the query.
        vector_hit = make_product("vector_hit", "Vector Only", "completely unrelated wording")
        vector_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add_all([keyword_hit, vector_hit])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        results, method, _ = search_hybrid(
            postgres_session, QUERY, provider, method=SearchMethod.HYBRID, limit=10,
        )

        result_ids = {p.id for p in results}
        assert method == SearchMethod.HYBRID
        assert "keyword_hit" in result_ids
        assert "vector_hit" in result_ids

    def test_rrf_ranks_dual_match_highest(self, postgres_session: Session):
        """Test that a product found by BOTH methods outranks ones found by only one
        (this is the defining behavior of RRF, not simple concatenation)."""
        provider = FakeEmbeddingProvider()

        # both_hit: exact query text as search_text AND embedding -> guaranteed
        # rank 1 in keyword search (best lexical match) and rank 1 in vector
        # search (distance exactly 0).
        both_hit = make_product("both_hit", "Both", QUERY)
        both_hit.embedding = provider.embed_passages([QUERY])[0]

        # Partial keyword match only (shares one token "zephyr"), with an
        # embedding of arbitrary unrelated text (non-zero distance).
        keyword_only = make_product("keyword_only", "Keyword Only", "zephyr accessory")
        keyword_only.embedding = provider.embed_passages(["arbitrary other text"])[0]

        postgres_session.add_all([both_hit, keyword_only])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        results, _, _ = search_hybrid(
            postgres_session, QUERY, provider, method=SearchMethod.HYBRID, limit=10,
        )

        result_ids = [p.id for p in results]
        assert "both_hit" in result_ids
        # both_hit holds rank 1 in both lists: combined RRF score 2/(60+1),
        # which exceeds any score a single-list-only product can achieve
        # (max 1/(60+1) for a rank-1-in-one-list product).
        assert result_ids.index("both_hit") == 0

    def test_hybrid_not_simple_concatenation(self, postgres_session: Session):
        """Test that hybrid results are deduplicated and re-ranked, not just
        vector results followed by keyword results concatenated."""
        provider = FakeEmbeddingProvider()

        # A product that would appear in BOTH raw result lists if it matches
        # both criteria -- concatenation without RRF's dedup would duplicate it.
        both_hit = make_product("both_hit", "Both", QUERY)
        both_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add(both_hit)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        results, _, _ = search_hybrid(
            postgres_session, QUERY, provider, method=SearchMethod.HYBRID, limit=10,
        )

        ids = [p.id for p in results]
        assert len(ids) == len(set(ids))
        assert ids.count("both_hit") == 1

    def test_vector_only_method(self, postgres_session: Session):
        """Test that method=VECTOR bypasses keyword search entirely."""
        provider = FakeEmbeddingProvider()

        keyword_hit = make_product("keyword_hit", "Keyword Only", "zephyr accessory")
        keyword_hit.embedding = provider.embed_passages(["unrelated content xyz"])[0]

        vector_hit = make_product("vector_hit", "Vector Only", "completely unrelated wording")
        vector_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add_all([keyword_hit, vector_hit])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        results, method, _ = search_hybrid(
            postgres_session, QUERY, provider, method=SearchMethod.VECTOR, limit=10,
        )

        assert method == SearchMethod.VECTOR
        # vector_hit has the exact-match embedding (distance 0), guaranteeing
        # it ranks first; vector search has no relevance threshold so
        # keyword_hit may still appear, just ranked behind it.
        assert results[0].id == "vector_hit"

    def test_keyword_only_method(self, postgres_session: Session):
        """Test that method=KEYWORD bypasses vector search entirely."""
        provider = FakeEmbeddingProvider()

        keyword_hit = make_product("keyword_hit", "Keyword Only", QUERY)
        keyword_hit.embedding = provider.embed_passages(["unrelated content xyz"])[0]

        vector_hit = make_product("vector_hit", "Vector Only", "completely unrelated wording")
        vector_hit.embedding = provider.embed_passages([QUERY])[0]

        postgres_session.add_all([keyword_hit, vector_hit])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        results, method, _ = search_hybrid(
            postgres_session, QUERY, provider, method=SearchMethod.KEYWORD, limit=10,
        )

        assert method == SearchMethod.KEYWORD
        result_ids = {p.id for p in results}
        assert "keyword_hit" in result_ids
        # vector_hit's search_text shares no tokens with the query, so
        # keyword (tsvector) search must not match it at all.
        assert "vector_hit" not in result_ids

    def test_hybrid_respects_filters(self, postgres_session: Session):
        """Test that filters apply consistently across both underlying searches."""
        provider = FakeEmbeddingProvider()
        p1 = make_product("p1", "Shirt", "blue shirt", gender="Men")
        p1.embedding = provider.embed_passages(["blue shirt"])[0]
        p2 = make_product("p2", "Shirt", "blue shirt", gender="Women")
        p2.embedding = provider.embed_passages(["blue shirt"])[0]
        postgres_session.add_all([p1, p2])
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        filters = SearchFilter(gender="Men")
        results, _, _ = search_hybrid(
            postgres_session, "blue shirt", provider,
            filters=filters, method=SearchMethod.HYBRID, limit=10,
        )

        assert all(p.gender == "Men" for p in results)
