"""Integration tests for LLM query understanding wired into POST /search.

Uses FakeEmbeddingProvider and FakeLLMProvider via dependency overrides -
never the real E5 model or the real Gemini API.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.routes.search as search_route
from app.main import app
from app.db.database import get_session
from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import QueryUnderstanding
from app.schemas.search import SearchFilter
from app.services.keyword_index import build_keyword_index

QUERY = "blue shirt for men"


def make_product(pid: str, name: str, search_text: str, **kwargs) -> Product:
    return Product(
        id=pid,
        external_product_id=f"ext_{pid}",
        name=name,
        search_text=search_text,
        content_hash=f"hash_{pid}",
        **kwargs,
    )


class TestSearchQueryUnderstanding:
    @pytest.fixture(autouse=True)
    def setup_client(self, postgres_session: Session):
        def override_get_session():
            yield postgres_session

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[search_route.get_search_provider] = lambda: FakeEmbeddingProvider()
        self.client = TestClient(app)
        self.session = postgres_session
        yield
        app.dependency_overrides.clear()

    def _seed_gendered_products(self):
        provider = FakeEmbeddingProvider()
        p_men = make_product("p_men", "Shirt", "blue cotton shirt", gender="Men")
        p_men.embedding = provider.embed_passages(["blue cotton shirt"])[0]
        p_women = make_product("p_women", "Shirt", "blue cotton shirt", gender="Women")
        p_women.embedding = provider.embed_passages(["blue cotton shirt"])[0]
        self.session.add_all([p_men, p_women])
        self.session.commit()
        build_keyword_index(self.session, limit=100)

    def test_llm_inferred_filter_is_applied_and_changes_results(self):
        self._seed_gendered_products()
        canned = QueryUnderstanding(
            cleaned_query="blue shirt",
            filters=SearchFilter(gender="Men"),
        )
        app.dependency_overrides[search_route.get_query_understanding_provider] = (
            lambda: FakeLLMProvider(canned_responses={QUERY: canned})
        )

        response = self.client.post("/search", json={"query": QUERY, "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) >= 1
        assert all(p["gender"] == "Men" for p in data["products"])

    def test_llm_failure_falls_back_to_original_query_behavior(self):
        self._seed_gendered_products()
        app.dependency_overrides[search_route.get_query_understanding_provider] = (
            lambda: FakeLLMProvider(raise_error=True)
        )

        response = self.client.post("/search", json={"query": QUERY, "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == QUERY
        # No filter was inferred (fallback), so both genders should be present.
        genders = {p["gender"] for p in data["products"]}
        assert genders == {"Men", "Women"}

    def test_explicit_user_filter_is_not_overridden_by_conflicting_llm_inference(self):
        self._seed_gendered_products()
        canned = QueryUnderstanding(
            cleaned_query="blue shirt",
            filters=SearchFilter(gender="Men"),
        )
        app.dependency_overrides[search_route.get_query_understanding_provider] = (
            lambda: FakeLLMProvider(canned_responses={QUERY: canned})
        )

        response = self.client.post(
            "/search",
            json={"query": QUERY, "filters": {"gender": "Women"}, "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) >= 1
        assert all(p["gender"] == "Women" for p in data["products"])

    def test_query_understanding_disabled_skips_llm_entirely(self, monkeypatch):
        self._seed_gendered_products()
        monkeypatch.setattr(search_route.settings, "query_understanding_enabled", False)
        spy = FakeLLMProvider(canned_responses={QUERY: QueryUnderstanding(cleaned_query="x", filters=SearchFilter(gender="Men"))})
        app.dependency_overrides[search_route.get_query_understanding_provider] = lambda: spy

        response = self.client.post("/search", json={"query": QUERY, "limit": 10})

        assert response.status_code == 200
        assert spy.calls == []
        genders = {p["gender"] for p in response.json()["products"]}
        assert genders == {"Men", "Women"}

    def test_new_catalogue_value_is_usable_by_llm_without_code_change(self):
        """A color that exists only in the DB (not in any hardcoded list) is accepted as an LLM filter."""
        provider = FakeEmbeddingProvider()
        for pid, color in (("lilac", "Lilac"), ("black", "Black")):
            product = make_product(pid, "Kurta", "cotton kurta", color=color)
            product.embedding = provider.embed_passages(["cotton kurta"])[0]
            self.session.add(product)
        self.session.commit()
        build_keyword_index(self.session, limit=100)
        canned = QueryUnderstanding(cleaned_query="cotton kurta", filters=SearchFilter(color="Lilac"))
        app.dependency_overrides[search_route.get_query_understanding_provider] = (
            lambda: FakeLLMProvider(canned_responses={"lilac cotton kurta": canned})
        )

        response = self.client.post(
            "/search", json={"query": "lilac cotton kurta", "method": "keyword", "limit": 10}
        )

        assert response.status_code == 200
        assert [p["id"] for p in response.json()["products"]] == ["lilac"]
