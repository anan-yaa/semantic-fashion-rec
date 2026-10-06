"""Repeat queries skip the LLM; failures are never cached."""
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import QueryUnderstanding
from app.schemas.search import SearchFilter
from app.services.query_understanding.service import understand_query
from core.config import settings

FACETS = {"gender": ["Men"], "category": [], "color": [], "season": []}
CANNED = QueryUnderstanding(cleaned_query="shirt", filters=SearchFilter(gender="Men"))


def test_second_identical_query_does_not_call_the_llm():
    llm = FakeLLMProvider(canned_responses={"Blue Shirt": CANNED})

    first = understand_query(llm, "Blue Shirt", FACETS)
    second = understand_query(llm, "  blue   shirt ", FACETS)

    assert llm.calls == ["Blue Shirt"]
    assert second.used_llm and second.filters.gender == first.filters.gender == "Men"


def test_fallbacks_are_not_cached():
    broken = FakeLLMProvider(raise_error=True)
    assert understand_query(broken, "shirt", FACETS).used_llm is False

    healthy = FakeLLMProvider()
    assert understand_query(healthy, "shirt", FACETS).used_llm is True


def test_ttl_zero_disables_the_cache(monkeypatch):
    monkeypatch.setattr(settings, "llm_cache_ttl_seconds", 0)
    llm = FakeLLMProvider()
    understand_query(llm, "shirt", FACETS)
    understand_query(llm, "shirt", FACETS)
    assert len(llm.calls) == 2
