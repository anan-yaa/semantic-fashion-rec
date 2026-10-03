"""Tests for search eval ranking metrics (pure functions, no DB)."""
import math

from app.services.eval.metrics import dcg_at_k, mrr, ndcg_at_k, precision_at_k, reciprocal_rank


class TestDcgAtK:
    def test_empty_list(self):
        assert dcg_at_k([], 10) == 0.0

    def test_single_relevant_at_rank_1(self):
        assert dcg_at_k([1], 10) == 1.0 / math.log2(2)

    def test_relevant_buried_at_rank_10_scores_less_than_at_rank_1(self):
        buried = [0] * 9 + [1]
        top = [1] + [0] * 9
        assert dcg_at_k(buried, 10) < dcg_at_k(top, 10)
        assert dcg_at_k(buried, 10) == 1.0 / math.log2(11)

    def test_k_beyond_list_length(self):
        assert dcg_at_k([1, 0, 1], 100) == dcg_at_k([1, 0, 1], 3)

    def test_k_truncates_list(self):
        assert dcg_at_k([1, 1, 1], 1) == 1.0 / math.log2(2)


class TestNdcgAtK:
    def test_perfect_ranking_is_1(self):
        assert ndcg_at_k([1, 1, 1, 0, 0], 5) == 1.0

    def test_no_relevant_items_is_zero_not_nan(self):
        result = ndcg_at_k([0, 0, 0], 10)
        assert result == 0.0
        assert not math.isnan(result)

    def test_worst_ranking_scores_less_than_perfect(self):
        worst = [0, 0, 1]  # relevant item buried last
        perfect = [1, 0, 0]  # same total relevance, but ranked first
        assert ndcg_at_k(worst, 3) < ndcg_at_k(perfect, 3)

    def test_single_relevant_item_is_perfect_regardless_of_position(self):
        # Binary-relevance NDCG invariant: with exactly one relevant item,
        # ideal DCG puts it first too, so any single-item relevance list
        # evaluated against itself as "ideal" isn't automatically 1.0 unless
        # it's actually at the front - verify both cases explicitly.
        assert ndcg_at_k([1], 10) == 1.0
        assert ndcg_at_k([0, 1], 10) < 1.0

    def test_empty_list(self):
        assert ndcg_at_k([], 10) == 0.0


class TestPrecisionAtK:
    def test_all_relevant(self):
        assert precision_at_k([1, 1, 1], 3) == 1.0

    def test_all_irrelevant(self):
        assert precision_at_k([0, 0, 0], 3) == 0.0

    def test_mixed(self):
        assert precision_at_k([1, 0, 1, 0], 4) == 0.5

    def test_short_list_pads_with_zeros_not_shrinking_denominator(self):
        # Only 2 results returned, k=10: should be 2/10, not 2/2.
        assert precision_at_k([1, 1], 10) == 0.2

    def test_k_zero(self):
        assert precision_at_k([1, 1], 0) == 0.0


class TestReciprocalRank:
    def test_relevant_at_rank_1(self):
        assert reciprocal_rank([1, 0, 0]) == 1.0

    def test_relevant_at_rank_3(self):
        assert reciprocal_rank([0, 0, 1]) == 1.0 / 3

    def test_no_relevant_items(self):
        assert reciprocal_rank([0, 0, 0]) == 0.0

    def test_empty_list(self):
        assert reciprocal_rank([]) == 0.0


class TestMrr:
    def test_averages_across_queries(self):
        lists = [[1, 0], [0, 1, 0], [0, 0, 0]]
        # reciprocal ranks: 1.0, 0.5, 0.0 -> mean 0.5
        assert mrr(lists) == 0.5

    def test_empty_input(self):
        assert mrr([]) == 0.0
