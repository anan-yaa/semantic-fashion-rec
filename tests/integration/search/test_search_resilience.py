"""503 on database outage, plus request IDs and CORS configuration."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.search import get_query_understanding_provider, get_search_provider
from app.db.database import get_session
from app.main import app
from app.providers.fake import FakeEmbeddingProvider
from app.providers.fake_llm import FakeLLMProvider


@pytest.fixture
def client(test_db):
    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_search_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_query_understanding_provider] = lambda: FakeLLMProvider()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_returns_503_when_database_is_down():
    unreachable = create_engine("postgresql+psycopg://u:p@127.0.0.1:1/none", connect_args={"connect_timeout": 1})

    def broken_session():
        with Session(unreachable) as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    app.dependency_overrides[get_search_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_query_understanding_provider] = lambda: FakeLLMProvider()
    try:
        response = TestClient(app).post("/search", json={"query": "shirt"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "127.0.0.1" not in response.text


def test_response_carries_a_request_id(client):
    response = client.post("/search", json={"query": "shirt"})
    assert response.headers["X-Request-ID"]


def test_caller_supplied_request_id_is_echoed(client):
    response = client.post("/search", json={"query": "shirt"}, headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_cors_allows_configured_origin_only(client):
    ok = client.options(
        "/search",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    bad = client.options(
        "/search",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers
