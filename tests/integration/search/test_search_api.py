"""Integration tests for POST /search endpoint against real PostgreSQL."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import get_session
from app.db.models.product import Product
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider
from app.api.routes.search import get_search_provider, get_query_understanding_provider
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


class TestSearchAPIIntegration:
    """Test suite for POST /search against real PostgreSQL + pgvector."""

    @pytest.fixture(autouse=True)
    def setup_client(self, postgres_session: Session):
        """Override DB dependency and force the fake embedding provider for API tests."""
        def override_get_session():
            yield postgres_session

        app.dependency_overrides[get_session] = override_get_session

        # Avoid loading the real e5 model in API integration tests.
        app.dependency_overrides[get_search_provider] = lambda: FakeEmbeddingProvider()
        # Avoid calling the real Gemini API in API integration tests.
        app.dependency_overrides[get_query_understanding_provider] = lambda: FakeLLMProvider()

        self.client = TestClient(app)
        self.session = postgres_session
        yield
        app.dependency_overrides.clear()

    def test_search_hybrid_returns_results(self):
        """Test POST /search with default (hybrid) method returns matching products."""
        both_hit = make_product("both_hit", "Both", QUERY)
        both_hit.embedding = FakeEmbeddingProvider().embed_passages([QUERY])[0]
        self.session.add(both_hit)
        self.session.commit()
        build_keyword_index(self.session, limit=100)

        response = self.client.post("/search", json={"query": QUERY, "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == QUERY
        assert data["method"] == "hybrid"
        assert any(p["id"] == "both_hit" for p in data["products"])
        assert data["took_ms"] >= 0

    def test_search_vector_method(self):
        """Test POST /search with method=vector."""
        p = make_product("p1", "Item", "unrelated text")
        p.embedding = FakeEmbeddingProvider().embed_passages([QUERY])[0]
        self.session.add(p)
        self.session.commit()

        response = self.client.post("/search", json={"query": QUERY, "method": "vector", "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "vector"
        assert data["products"][0]["id"] == "p1"

    def test_search_keyword_method(self):
        """Test POST /search with method=keyword."""
        p = make_product("p1", "Item", QUERY)
        self.session.add(p)
        self.session.commit()
        build_keyword_index(self.session, limit=100)

        response = self.client.post("/search", json={"query": QUERY, "method": "keyword", "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "keyword"
        assert any(p["id"] == "p1" for p in data["products"])

    def test_search_with_filters(self):
        """Test POST /search applies filters."""
        p1 = make_product("p1", "Shirt", "blue shirt", gender="Men")
        p1.embedding = FakeEmbeddingProvider().embed_passages(["blue shirt"])[0]
        p2 = make_product("p2", "Shirt", "blue shirt", gender="Women")
        p2.embedding = FakeEmbeddingProvider().embed_passages(["blue shirt"])[0]
        self.session.add_all([p1, p2])
        self.session.commit()
        build_keyword_index(self.session, limit=100)

        response = self.client.post("/search", json={
            "query": "blue shirt",
            "filters": {"gender": "Men"},
            "limit": 10,
        })

        assert response.status_code == 200
        data = response.json()
        assert all(p["gender"] == "Men" for p in data["products"])

    def test_search_empty_query_rejected(self):
        """Test that an empty query string is rejected by validation."""
        response = self.client.post("/search", json={"query": "", "limit": 10})

        assert response.status_code == 422

    def test_search_invalid_method_rejected(self):
        """Test that an invalid search method is rejected by the Enum schema."""
        response = self.client.post("/search", json={"query": "shirt", "method": "not_a_method"})

        assert response.status_code == 422

    def test_search_no_results(self):
        """Test POST /search returns empty list when nothing matches."""
        response = self.client.post("/search", json={"query": "nonexistent query xyz", "limit": 10})

        assert response.status_code == 200
        data = response.json()
        assert data["products"] == []
        assert data["total_products"] == 0

    def test_search_response_schema(self):
        """Test the response schema matches SearchResponse exactly."""
        p = make_product("p1", "Item", QUERY)
        p.embedding = FakeEmbeddingProvider().embed_passages([QUERY])[0]
        self.session.add(p)
        self.session.commit()
        build_keyword_index(self.session, limit=100)

        response = self.client.post("/search", json={"query": QUERY, "limit": 10})

        data = response.json()
        assert set(data.keys()) == {"products", "query", "method", "total_products", "took_ms"}
        for product in data["products"]:
            assert "embedding" not in product
            assert "content_hash" not in product
            assert "search_vector" not in product

    def _seed_availability_pair(self):
        provider = FakeEmbeddingProvider()
        for pid, available in (("in_stock", True), ("delisted", False)):
            product = make_product(pid, pid, QUERY, availability=available)
            product.embedding = provider.embed_passages([QUERY])[0]
            self.session.add(product)
        self.session.commit()
        build_keyword_index(self.session, limit=100)

    @pytest.mark.parametrize("method", ["hybrid", "vector", "keyword"])
    def test_unavailable_products_hidden_by_default(self, method):
        self._seed_availability_pair()

        response = self.client.post("/search", json={"query": QUERY, "method": method, "limit": 10})

        assert response.status_code == 200
        assert [p["id"] for p in response.json()["products"]] == ["in_stock"]

    def test_unavailable_products_returned_when_requested(self):
        self._seed_availability_pair()

        response = self.client.post(
            "/search", json={"query": QUERY, "filters": {"availability": False}, "limit": 10}
        )

        assert response.status_code == 200
        assert [p["id"] for p in response.json()["products"]] == ["delisted"]
