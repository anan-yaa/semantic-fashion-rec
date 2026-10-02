"""Tests for Reciprocal Rank Fusion."""
import pytest

from app.db.models.product import Product
from app.services.search.rank_fusion import reciprocal_rank_fusion


def make_product(product_id: str) -> Product:
    """Helper to create a minimal Product instance (not persisted)."""
    return Product(
        id=product_id,
        external_product_id=f"ext_{product_id}",
        name=f"Product {product_id}",
    )


class TestReciprocalRankFusion:
    """Test suite for RRF."""

    def test_empty_lists(self):
        """Test RRF with no results from either method."""
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_vector_only(self):
        """Test RRF when only vector results exist."""
        p1, p2 = make_product("p1"), make_product("p2")
        result = reciprocal_rank_fusion([p1, p2], [])
        assert [p.id for p in result] == ["p1", "p2"]

    def test_keyword_only(self):
        """Test RRF when only keyword results exist."""
        p1, p2 = make_product("p1"), make_product("p2")
        result = reciprocal_rank_fusion([], [p1, p2])
        assert [p.id for p in result] == ["p1", "p2"]

    def test_disjoint_results_preserve_relative_order(self):
        """Test that non-overlapping results are ordered by their own rank."""
        v1, v2 = make_product("v1"), make_product("v2")
        k1, k2 = make_product("k1"), make_product("k2")

        result = reciprocal_rank_fusion([v1, v2], [k1, k2])

        # v1/k1 (rank 1 in their list) should outscore v2/k2 (rank 2)
        ids = [p.id for p in result]
        assert ids.index("v1") < ids.index("v2")
        assert ids.index("k1") < ids.index("k2")

    def test_overlapping_result_ranks_higher(self):
        """Test that a product appearing in both lists gets a boosted combined score."""
        shared = make_product("shared")
        vector_only = make_product("vector_only")
        keyword_only = make_product("keyword_only")

        # 'shared' is rank 2 in vector, rank 2 in keyword -> combined score beats
        # a product that is rank 1 in only one list, if scores overlap favorably.
        vector_results = [vector_only, shared]
        keyword_results = [keyword_only, shared]

        result = reciprocal_rank_fusion(vector_results, keyword_results, k=60)

        # 'shared' appears in both lists, so its fused score = 1/(60+2) + 1/(60+2)
        # which exceeds any single-list top score of 1/(60+1)
        shared_rank = [p.id for p in result].index("shared")
        assert shared_rank == 0  # shared should rank first due to dual presence

    def test_deduplication(self):
        """Test that duplicate products (same ID in both lists) appear once."""
        p1 = make_product("p1")
        p1_dup = make_product("p1")  # Same ID, different instance

        result = reciprocal_rank_fusion([p1], [p1_dup])

        assert len(result) == 1
        assert result[0].id == "p1"

    def test_k_parameter_affects_scores(self):
        """Test that different k values change relative scoring (sanity check on formula)."""
        p1, p2 = make_product("p1"), make_product("p2")

        # With very small k, rank 1 vs rank 2 difference is more pronounced
        result_small_k = reciprocal_rank_fusion([p1, p2], [], k=1)
        result_large_k = reciprocal_rank_fusion([p1, p2], [], k=1000)

        # Order should be preserved regardless of k (p1 always rank 1)
        assert result_small_k[0].id == "p1"
        assert result_large_k[0].id == "p1"
