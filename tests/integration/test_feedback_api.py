"""Integration tests for search-result feedback (POST /feedback, GET /feedback/votes, /feedback/summary)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import rate_limit
from app.api.rate_limit import TokenBucketLimiter
from app.db.database import get_session
from app.db.models.feedback import SearchFeedback
from app.db.models.product import Product
from app.main import app
from app.services.feedback import normalize_query

CLIENT = "client-aaaa-1111"
OTHER = "client-bbbb-2222"


@pytest.fixture
def client(test_db):
    for pid, name in (("p1", "Red Dress"), ("p2", "Blue Shirt"), ("p3", "Black Jacket")):
        test_db.add(Product(id=pid, external_product_id=f"ext_{pid}", name=name, search_text=name.lower(),
                            content_hash=f"h_{pid}"))
    test_db.commit()

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def vote(client, product_id="p1", value=1, query="red dress", client_id=CLIENT, **extra):
    body = {"client_id": client_id, "query": query, "product_id": product_id, "vote": value, "position": 1, **extra}
    return client.post("/feedback", json=body)


def votes(client, query="red dress", client_id=CLIENT):
    return client.get("/feedback/votes", params={"client_id": client_id, "query": query}).json()["votes"]


class TestSubmit:
    def test_records_a_vote_with_its_context(self, client, test_db):
        response = vote(
            client, value=-1, method="hybrid", sort="newest", filters={"gender": "Women"},
            understanding={"used_llm": True, "translated": True, "english_query": "red dress",
                           "inferred_filters": {"color": "Red"},
                           "fallback_reason": None},
        )

        assert response.status_code == 200
        assert response.json() == {"vote": -1}
        row = test_db.query(SearchFeedback).one()
        assert (row.vote, row.search_method, row.sort) == (-1, "hybrid", "newest")
        assert row.filters == {"gender": "Women"}
        assert row.llm_used is True and row.llm_keywords == "red dress"
        assert row.llm_filters == {"color": "Red"}

    def test_voting_again_replaces_the_vote(self, client, test_db):
        vote(client, value=1)
        vote(client, value=-1)

        assert test_db.query(SearchFeedback).count() == 1
        assert votes(client) == {"p1": -1}

    def test_vote_zero_removes_the_vote(self, client, test_db):
        vote(client, value=1)

        assert vote(client, value=0).json() == {"vote": 0}
        assert test_db.query(SearchFeedback).count() == 0

    def test_removing_a_missing_vote_is_harmless(self, client):
        assert vote(client, value=0).status_code == 200

    def test_unknown_product_is_404(self, client):
        assert vote(client, product_id="nope").status_code == 404

    @pytest.mark.parametrize(
        "change",
        [{"vote": 2}, {"position": 0}, {"client_id": "x"}, {"client_id": "bad id with spaces"}, {"query": ""}],
    )
    def test_invalid_requests_are_422(self, client, change):
        body = {"client_id": CLIENT, "query": "q", "product_id": "p1", "vote": 1, "position": 1, **change}
        assert client.post("/feedback", json=body).status_code == 422


class TestVotes:
    def test_same_query_with_different_spacing_and_case_matches(self, client):
        vote(client, query="  Red   DRESS ")

        assert votes(client, query="red dress") == {"p1": 1}

    def test_only_this_clients_votes_for_this_query(self, client):
        vote(client, product_id="p1", value=1)
        vote(client, product_id="p2", value=-1)
        vote(client, product_id="p3", value=1, client_id=OTHER)
        vote(client, product_id="p3", value=1, query="black jacket")

        assert votes(client) == {"p1": 1, "p2": -1}


class TestSummary:
    def test_empty(self, client):
        summary = client.get("/feedback/summary").json()

        assert summary["total_votes"] == 0
        assert summary["helpful_rate"] is None
        assert summary["most_not_helpful"] == [] and summary["recent"] == []

    def test_totals_and_worst_queries(self, client):
        vote(client, product_id="p1", value=-1, query="red dress")
        vote(client, product_id="p2", value=-1, query="Red Dress")
        vote(client, product_id="p3", value=1, query="red dress", client_id=OTHER)
        vote(client, product_id="p3", value=-1, query="black jacket")
        vote(client, product_id="p2", value=1, query="blue shirt")

        summary = client.get("/feedback/summary").json()

        assert (summary["total_votes"], summary["helpful"], summary["not_helpful"]) == (5, 2, 3)
        assert summary["helpful_rate"] == pytest.approx(0.4)
        assert (summary["queries"], summary["clients"]) == (3, 2)
        worst = [(q["query"].lower(), q["helpful"], q["not_helpful"]) for q in summary["most_not_helpful"]]
        assert worst == [("red dress", 1, 2), ("black jacket", 0, 1)]

    def test_recent_includes_product_names(self, client):
        vote(client, product_id="p3", value=1, query="black jacket")

        recent = client.get("/feedback/summary").json()["recent"]

        assert recent[0]["product_name"] == "Black Jacket"
        assert recent[0]["query"] == "black jacket"


def test_normalize_query():
    assert normalize_query("  Black   Leather JACKET ") == "black leather jacket"


def test_feedback_is_rate_limited(client):
    limiter = TokenBucketLimiter(rate_per_minute=60, burst=2, clock=lambda: 1000.0)
    with patch.object(rate_limit, "feedback_rate_limiter", limiter), \
            patch.object(rate_limit.settings, "rate_limit_enabled", True):
        assert [vote(client).status_code for _ in range(3)] == [200, 200, 429]
        assert client.get("/feedback/summary").status_code == 200
