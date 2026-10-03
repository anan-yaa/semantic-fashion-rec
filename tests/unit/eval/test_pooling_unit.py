"""Tests for pool dedup/union logic against a stubbed search_hybrid (no DB)."""
from unittest.mock import MagicMock

import app.services.eval.pooling as pooling_module
from app.db.models.product import Product
from app.schemas.search import SearchMethod
from app.services.eval.io import QuerySetEntry
from app.services.eval.pooling import build_pool


def make_product(pid: str, name: str = "Test Product") -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        category="Apparel",
        subcategory="Topwear",
        gender="Men",
        color="Black",
        season="Summer",
        search_text="test product",
        content_hash=f"hash_{pid}",
    )


def stub_search_hybrid(vector_ids, keyword_ids, hybrid_ids):
    """Builds a fake search_hybrid that returns different product sets per method."""
    by_method = {
        SearchMethod.VECTOR: [make_product(pid) for pid in vector_ids],
        SearchMethod.KEYWORD: [make_product(pid) for pid in keyword_ids],
        SearchMethod.HYBRID: [make_product(pid) for pid in hybrid_ids],
    }

    def fake(session, query_text, provider, filters=None, method=SearchMethod.HYBRID, limit=50):
        return by_method[method], method, 1.0

    return fake


class TestBuildPool:
    def test_union_deduplicates_overlapping_candidates(self, monkeypatch):
        # "both" appears in vector and keyword; pool should contain it once.
        monkeypatch.setattr(
            pooling_module,
            "search_hybrid",
            stub_search_hybrid(
                vector_ids=["both", "vector_only"],
                keyword_ids=["both", "keyword_only"],
                hybrid_ids=["both"],
            ),
        )

        queries = [QuerySetEntry(id="q1", query="test query", category_tag="keyword_heavy")]
        pools, stats = build_pool(MagicMock(), MagicMock(), queries)

        assert len(pools) == 1
        candidate_ids = {c.product_id for c in pools[0].candidates}
        assert candidate_ids == {"both", "vector_only", "keyword_only"}
        assert stats.total_candidates == 3

    def test_found_by_reflects_all_methods_that_retrieved_it(self, monkeypatch):
        monkeypatch.setattr(
            pooling_module,
            "search_hybrid",
            stub_search_hybrid(
                vector_ids=["both", "vector_only"],
                keyword_ids=["both"],
                hybrid_ids=["both"],
            ),
        )

        queries = [QuerySetEntry(id="q1", query="test query", category_tag="keyword_heavy")]
        pools, _ = build_pool(MagicMock(), MagicMock(), queries)

        by_id = {c.product_id: c for c in pools[0].candidates}
        assert set(by_id["both"].found_by) == {"vector", "keyword", "hybrid"}
        assert set(by_id["vector_only"].found_by) == {"vector"}

    def test_pre_label_initialized_to_none(self, monkeypatch):
        monkeypatch.setattr(
            pooling_module,
            "search_hybrid",
            stub_search_hybrid(vector_ids=["p1"], keyword_ids=[], hybrid_ids=[]),
        )

        queries = [QuerySetEntry(id="q1", query="test query", category_tag="keyword_heavy")]
        pools, _ = build_pool(MagicMock(), MagicMock(), queries)

        assert pools[0].candidates[0].pre_label is None
        assert pools[0].candidates[0].pre_label_rationale is None

    def test_pool_size_is_union_not_sum(self, monkeypatch):
        # All 3 methods return the exact same single product - pool must have 1, not 3.
        monkeypatch.setattr(
            pooling_module,
            "search_hybrid",
            stub_search_hybrid(vector_ids=["p1"], keyword_ids=["p1"], hybrid_ids=["p1"]),
        )

        queries = [QuerySetEntry(id="q1", query="test query", category_tag="keyword_heavy")]
        pools, stats = build_pool(MagicMock(), MagicMock(), queries)

        assert len(pools[0].candidates) == 1
        assert stats.total_candidates == 1

    def test_multiple_queries_produce_separate_pools(self, monkeypatch):
        monkeypatch.setattr(
            pooling_module,
            "search_hybrid",
            stub_search_hybrid(vector_ids=["p1"], keyword_ids=["p2"], hybrid_ids=[]),
        )

        queries = [
            QuerySetEntry(id="q1", query="first", category_tag="keyword_heavy"),
            QuerySetEntry(id="q2", query="second", category_tag="vague"),
        ]
        pools, stats = build_pool(MagicMock(), MagicMock(), queries)

        assert len(pools) == 2
        assert stats.query_count == 2
        assert {p.query_id for p in pools} == {"q1", "q2"}
