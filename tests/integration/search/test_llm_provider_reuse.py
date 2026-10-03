"""End-to-end proof that POST /search reuses a single LLM provider instance
across requests instead of constructing a new one per request.

Mirrors tests/integration/search/test_search_provider_reuse.py for the
embedding provider.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.routes.search as search_route
from app.main import app
from app.db.database import get_session
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider


class CountingLLMProvider(FakeLLMProvider):
    """Fake LLM provider that records how many times it was constructed and used."""

    instances_created = 0

    def __init__(self):
        super().__init__()
        CountingLLMProvider.instances_created += 1

    @classmethod
    def reset(cls):
        cls.instances_created = 0


@pytest.fixture(autouse=True)
def reset_provider_state():
    search_route._reset_search_provider_cache()
    search_route._reset_query_understanding_provider_cache()
    CountingLLMProvider.reset()
    yield
    search_route._reset_search_provider_cache()
    search_route._reset_query_understanding_provider_cache()
    CountingLLMProvider.reset()


class TestLLMProviderReuse:
    @pytest.fixture(autouse=True)
    def setup_client(self, postgres_session: Session):
        def override_get_session():
            yield postgres_session

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[search_route.get_search_provider] = lambda: FakeEmbeddingProvider()
        self.client = TestClient(app)
        yield
        app.dependency_overrides.clear()

    def test_application_startup_does_not_construct_llm_provider(self):
        assert search_route._llm_provider is None

    def test_multiple_requests_reuse_the_same_llm_provider_instance(self, monkeypatch):
        monkeypatch.setattr(
            search_route,
            "get_llm_provider",
            lambda settings, use_fake=False: CountingLLMProvider(),
        )

        r1 = self.client.post("/search", json={"query": "shirt", "limit": 5})
        r2 = self.client.post("/search", json={"query": "shoes", "limit": 5})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert CountingLLMProvider.instances_created == 1

        provider = search_route._llm_provider
        assert isinstance(provider, CountingLLMProvider)
        assert provider.calls == ["shirt", "shoes"]
