"""Integration tests for run_eval() against real PostgreSQL.

Uses FakeEmbeddingProvider (never the real E5 model) and hand-built ground
truth (bypassing the labeling CLI entirely) - the point here is testing
run_eval()'s wiring and metric computation, not real embedding quality.
"""
from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import QueryUnderstanding
from app.schemas.search import SearchFilter
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
            assert 0.0 <= scores.mrr_at_10 <= scores.mrr
            assert 0.0 <= scores.recall_at_10 <= scores.recall_at_20 <= scores.recall_at_50 <= 1.0

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

    def test_llm_provider_omitted_matches_original_behavior(self, postgres_session: Session):
        """Default (no llm_provider) must be byte-for-byte unaffected by its addition."""
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        judgments = [GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=["p1"])]
        report = run_eval(postgres_session, provider, judgments, k=10)

        assert report.query_understanding_enabled is False
        assert report.query_understanding == []

    def test_llm_provider_cleans_keyword_query_and_is_recorded(self, postgres_session: Session):
        """With an llm_provider, the cleaned query must reach keyword search
        (letting it find a product the raw, filler-heavy query would miss -
        the exact production failure mode this feature targets) and the
        outcome must be recorded in the report for analysis.
        """
        provider = FakeEmbeddingProvider()
        raw_query = "something comfortable for a zephyr day"
        cleaned = "zephyr product"

        p1 = make_product("p1", "Product One", cleaned)
        p1.embedding = provider.embed_passages([raw_query])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        llm_provider = FakeLLMProvider(
            canned_responses={
                raw_query: QueryUnderstanding(cleaned_query=cleaned, filters=SearchFilter())
            }
        )
        judgments = [GroundTruthEntry(query_id="q1", query=raw_query, relevant_product_ids=["p1"])]
        report = run_eval(postgres_session, provider, judgments, k=10, llm_provider=llm_provider)

        assert report.query_understanding_enabled is True
        assert len(report.query_understanding) == 1
        record = report.query_understanding[0]
        assert record.query_id == "q1"
        assert record.used_llm is True
        assert record.cleaned_query == cleaned

        # The cleaned query (whose tokens all appear in p1's search_text) must
        # have reached keyword search - the raw query's filler words would
        # otherwise fail plainto_tsquery's AND-semantics against it.
        assert report.per_method["keyword"].ndcg_at_10 == 1.0

    def test_llm_provider_failure_falls_back_and_is_recorded(self, postgres_session: Session):
        provider = FakeEmbeddingProvider()

        p1 = make_product("p1", "Product One", QUERY)
        p1.embedding = provider.embed_passages([QUERY])[0]
        postgres_session.add(p1)
        postgres_session.commit()
        build_keyword_index(postgres_session, limit=100)

        llm_provider = FakeLLMProvider(raise_error=True)
        judgments = [GroundTruthEntry(query_id="q1", query=QUERY, relevant_product_ids=["p1"])]
        report = run_eval(postgres_session, provider, judgments, k=10, llm_provider=llm_provider)

        assert report.query_understanding_enabled is True
        record = report.query_understanding[0]
        assert record.used_llm is False
        assert record.cleaned_query == QUERY
        assert record.error is not None
        # Fallback must still let the original query reach keyword search.
        assert report.per_method["keyword"].ndcg_at_10 == 1.0
