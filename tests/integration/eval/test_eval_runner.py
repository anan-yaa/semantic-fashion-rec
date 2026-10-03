"""Integration tests for run_eval() against real PostgreSQL.

Uses FakeEmbeddingProvider (never the real E5 model) and hand-built ground
truth (bypassing the labeling CLI entirely) - the point here is testing
run_eval()'s wiring and metric computation, not real embedding quality.
"""
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.services.eval import GroundTruthEntry, run_eval
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


class TestRunEvalIntegration:
    def test_scores_are_in_valid_range(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        judgments = [GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=["p1"])]
        report = run_eval(postgres_session, provider, judgments, k=10)

        assert report.query_count == 1
        assert report.excluded_query_count == 0
        for method, scores in report.per_method.items():
            assert 0.0 <= scores.ndcg_at_10 <= 1.0
            assert 0.0 <= scores.precision_at_10 <= 1.0
            assert 0.0 <= scores.mrr <= 1.0

    def test_vector_findable_only_item_scores_zero_on_keyword_method(self, postgres_session: Session):
        """A relevant product only findable via semantic/vector match (unrelated
        search_text, exact-match embedding) must score 0 NDCG on keyword-only
        search, but perfect NDCG on vector/hybrid - a regression guard on the
        metric wiring, not a claim about real embedding quality."""
        provider = FakeEmbeddingProvider()

        vector_only_relevant = make_product(
            "vector_only", "Semantic Match", "completely unrelated wording"
        )
        vector_only_relevant.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(vector_only_relevant)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        judgments = [
            GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=["vector_only"])
        ]
        report = run_eval(postgres_session, provider, judgments, k=10)

        assert report.per_method["keyword"].ndcg_at_10 == 0.0
        assert report.per_method["vector"].ndcg_at_10 == 1.0
        assert report.per_method["hybrid"].ndcg_at_10 == 1.0

    def test_query_with_no_relevant_items_is_excluded_from_aggregate(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        judgments = [GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=[])]
        report = run_eval(postgres_session, provider, judgments, k=10)

        assert report.excluded_query_count == 1
        assert report.query_count == 0
        assert report.per_method == {}

    def test_per_query_breakdown_matches_per_method_keys(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        judgments = [GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=["p1"])]
        report = run_eval(postgres_session, provider, judgments, k=10)

        assert "q1" in report.per_query
        assert set(report.per_query["q1"].keys()) == {"hybrid", "vector", "keyword"}
