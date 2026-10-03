"""Unit tests for FakeLLMProvider - deterministic, never calls a real API."""
import pytest

from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import LLMProviderError, QueryUnderstanding
from app.schemas.search import SearchFilter

VALID_FILTERS = {
    "category": ["Apparel", "Footwear"],
    "gender": ["Men", "Women"],
    "color": ["Black", "Blue"],
    "season": ["Summer", "Winter"],
}


class TestFakeLLMProvider:
    def test_default_behavior_returns_query_unchanged_with_no_filters(self):
        provider = FakeLLMProvider()

        result = provider.understand_query("blue running shoes", VALID_FILTERS)

        assert result.cleaned_query == "blue running shoes"
        assert result.filters == SearchFilter()

    def test_canned_response_is_returned_for_exact_query_match(self):
        canned = QueryUnderstanding(
            cleaned_query="running shoes",
            filters=SearchFilter(color="Blue"),
        )
        provider = FakeLLMProvider(canned_responses={"blue running shoes": canned})

        result = provider.understand_query("blue running shoes", VALID_FILTERS)

        assert result is canned

    def test_unlisted_query_falls_back_to_default_behavior_even_with_canned_responses(self):
        canned = QueryUnderstanding(cleaned_query="x", filters=SearchFilter())
        provider = FakeLLMProvider(canned_responses={"some other query": canned})

        result = provider.understand_query("blue running shoes", VALID_FILTERS)

        assert result.cleaned_query == "blue running shoes"

    def test_raise_error_flag_raises_llm_provider_error(self):
        provider = FakeLLMProvider(raise_error=True)

        with pytest.raises(LLMProviderError):
            provider.understand_query("blue running shoes", VALID_FILTERS)

    def test_records_every_call(self):
        provider = FakeLLMProvider()

        provider.understand_query("a", VALID_FILTERS)
        provider.understand_query("b", VALID_FILTERS)

        assert provider.calls == ["a", "b"]

    def test_never_returns_a_value_outside_the_valid_filters_passed_in(self):
        canned = QueryUnderstanding(
            cleaned_query="shoes",
            filters=SearchFilter(category="Apparel", gender="Men", color="Blue", season="Summer"),
        )
        provider = FakeLLMProvider(canned_responses={"q": canned})

        result = provider.understand_query("q", VALID_FILTERS)

        for field_name in ("category", "gender", "color", "season"):
            value = getattr(result.filters, field_name)
            assert value is None or value in VALID_FILTERS[field_name]
