"""End-to-end proof that POST /search reuses a single embedding provider
instance across requests instead of constructing/loading one per request.

Complements:
- tests/unit/search/test_search_provider_singleton.py (dependency-level
  caching, no HTTP involved)
- tests/unit/providers/test_e5_prefixes.py::test_lazy_model_loading
  (the provider itself only loads the model weights once)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.routes.search as search_route
from app.db.database import get_session
from app.main import app
from app.providers.fake import FakeEmbeddingProvider


class CountingProvider(FakeEmbeddingProvider):
    """Fake provider that records how many times it was constructed and used."""

    instances_created = 0

    def __init__(self):
        CountingProvider.instances_created += 1
        self.embed_passages_calls = 0
        self.embed_queries_calls = 0

    def embed_passages(self, texts):
        self.embed_passages_calls += 1
        return super().embed_passages(texts)

    def embed_queries(self, texts):
        self.embed_queries_calls += 1
        return super().embed_queries(texts)

    @classmethod
    def reset(cls):
        cls.instances_created = 0


@pytest.fixture(autouse=True)
def reset_provider_state():
    search_route._reset_search_provider_cache()
    CountingProvider.reset()
    yield
    search_route._reset_search_provider_cache()
    CountingProvider.reset()


class TestSearchProviderReuse:
    """Test suite proving provider reuse through the real HTTP/DI stack."""

    @pytest.fixture(autouse=True)
    def setup_client(self, postgres_session: Session):
        def override_get_session():
            yield postgres_session

        app.dependency_overrides[get_session] = override_get_session
        self.client = TestClient(app)
        yield
        app.dependency_overrides.clear()

    def test_application_startup_does_not_construct_provider(self):
        """Creating the app/TestClient must not eagerly build the provider."""
        assert search_route._provider is None

    def test_keyword_search_never_touches_the_provider(self, monkeypatch):
        """method=keyword must not construct or call the embedding provider."""
        spy = CountingProvider()
        monkeypatch.setattr(search_route, "_provider", spy)

        response = self.client.post(
            "/search", json={"query": "anything", "method": "keyword", "limit": 5}
        )

        assert response.status_code == 200
        assert spy.embed_queries_calls == 0
        assert spy.embed_passages_calls == 0

    def test_multiple_vector_requests_reuse_the_same_provider_instance(self, monkeypatch):
        """Two vector-method requests must share one provider instance.

        This is the regression test for the bug where app/api/routes/search.py
        called get_embedding_provider(settings, use_fake=False) directly inside
        the route body, constructing (and therefore lazily reloading) a brand
        new HuggingFaceE5Provider on every single request.
        """
        monkeypatch.setattr(
            search_route,
            "get_embedding_provider",
            lambda settings, use_fake=False: CountingProvider(),
        )

        r1 = self.client.post("/search", json={"query": "shirt", "method": "vector", "limit": 5})
        r2 = self.client.post("/search", json={"query": "shoes", "method": "vector", "limit": 5})

        assert r1.status_code == 200
        assert r2.status_code == 200

        # The factory must only have been invoked once across both requests.
        assert CountingProvider.instances_created == 1

        # The single instance must have served both requests.
        provider = search_route._provider
        assert isinstance(provider, CountingProvider)
        assert provider.embed_queries_calls == 2

    def test_hybrid_requests_also_reuse_the_same_provider_instance(self, monkeypatch):
        monkeypatch.setattr(
            search_route,
            "get_embedding_provider",
            lambda settings, use_fake=False: CountingProvider(),
        )

        for _ in range(3):
            response = self.client.post(
                "/search", json={"query": "jacket", "method": "hybrid", "limit": 5}
            )
            assert response.status_code == 200

        assert CountingProvider.instances_created == 1
