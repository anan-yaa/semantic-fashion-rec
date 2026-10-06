"""POST /search reports per-stage durations in the Server-Timing header."""
import pytest
from fastapi.testclient import TestClient

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


def _stages(response):
    return {
        part.split(";")[0].strip(): float(part.split("dur=")[1])
        for part in response.headers["Server-Timing"].split(",")
    }


def test_hybrid_search_reports_each_stage(client):
    stages = _stages(client.post("/search", json={"query": "shirt"}))

    assert {"facets", "llm", "types", "embed", "vector_db", "keyword_db", "total"} <= set(stages)
    assert all(ms >= 0 for ms in stages.values())
    assert stages["total"] >= stages["llm"]


def test_keyword_search_has_no_vector_stages(client):
    stages = _stages(client.post("/search", json={"query": "shirt", "method": "keyword"}))

    assert "keyword_db" in stages
    assert "embed" not in stages and "vector_db" not in stages
