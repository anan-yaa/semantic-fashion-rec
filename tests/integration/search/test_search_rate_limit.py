"""POST /search rate limiting through the real route (SQLite, fake models)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import rate_limit
from app.api.rate_limit import TokenBucketLimiter
from app.api.routes.search import get_query_understanding_provider, get_search_provider
from app.db.database import get_session
from app.main import app
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider


class FrozenClock:
    def __call__(self):
        return 1000.0


@pytest.fixture
def client(test_db):
    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_search_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_query_understanding_provider] = lambda: FakeLLMProvider()
    limiter = TokenBucketLimiter(rate_per_minute=30, burst=3, clock=FrozenClock())
    with patch.object(rate_limit, "search_rate_limiter", limiter), \
            patch.object(rate_limit.settings, "rate_limit_enabled", True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def search(client, headers=None):
    return client.post("/search", json={"query": "shirt", "method": "keyword"}, headers=headers or {})


def test_burst_then_429_with_retry_after(client):
    assert [search(client).status_code for _ in range(3)] == [200, 200, 200]

    response = search(client)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    assert response.json() == {"detail": "Too many searches. Try again in 2 seconds."}


def test_browsing_is_not_limited(client):
    for _ in range(3):
        search(client)
    assert search(client).status_code == 429

    assert client.get("/products").status_code == 200
    assert client.get("/products/facets").status_code == 200


def test_disabled_means_unlimited(client):
    with patch.object(rate_limit.settings, "rate_limit_enabled", False):
        assert all(search(client).status_code == 200 for _ in range(10))


def test_forwarded_header_ignored_unless_trusted(client):
    for i in range(3):
        search(client, {"X-Forwarded-For": f"10.0.0.{i}"})

    assert search(client, {"X-Forwarded-For": "10.0.0.99"}).status_code == 429


def test_trusted_proxy_limits_each_forwarded_client(client):
    with patch.object(rate_limit.settings, "trust_proxy_headers", True):
        for _ in range(3):
            search(client, {"X-Forwarded-For": "1.1.1.1"})
        assert search(client, {"X-Forwarded-For": "1.1.1.1"}).status_code == 429
        assert search(client, {"X-Forwarded-For": "2.2.2.2"}).status_code == 200
        # The proxy appends the real client last; an earlier, client-sent entry can't dodge the limit.
        assert search(client, {"X-Forwarded-For": "9.9.9.9, 1.1.1.1"}).status_code == 429
