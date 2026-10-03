"""Tests for the search route's LLM provider singleton.

Mirrors tests/unit/search/test_search_provider_singleton.py for the
embedding provider. See tests/integration/search/test_llm_provider_reuse.py
for the end-to-end proof through the API.
"""
import pytest

import app.api.routes.search as search_route
from app.providers.fake_llm import FakeLLMProvider


@pytest.fixture(autouse=True)
def reset_provider_cache():
    """Ensure each test starts from a clean, uncached state."""
    search_route._reset_query_understanding_provider_cache()
    yield
    search_route._reset_query_understanding_provider_cache()


def test_get_query_understanding_provider_returns_same_instance_across_calls():
    first = search_route.get_query_understanding_provider()
    second = search_route.get_query_understanding_provider()
    assert first is second


def test_get_query_understanding_provider_calls_factory_exactly_once(monkeypatch):
    call_count = {"n": 0}

    def counting_factory(settings, use_fake=False):
        call_count["n"] += 1
        return FakeLLMProvider()

    monkeypatch.setattr(search_route, "get_llm_provider", counting_factory)

    search_route.get_query_understanding_provider()
    search_route.get_query_understanding_provider()
    search_route.get_query_understanding_provider()

    assert call_count["n"] == 1


def test_reset_cache_forces_a_new_instance(monkeypatch):
    call_count = {"n": 0}

    def counting_factory(settings, use_fake=False):
        call_count["n"] += 1
        return FakeLLMProvider()

    monkeypatch.setattr(search_route, "get_llm_provider", counting_factory)

    first = search_route.get_query_understanding_provider()
    search_route._reset_query_understanding_provider_cache()
    second = search_route.get_query_understanding_provider()

    assert first is not second
    assert call_count["n"] == 2


def test_provider_not_constructed_until_first_call(monkeypatch):
    """Importing/defining the dependency must not eagerly create a provider."""
    assert search_route._llm_provider is None
