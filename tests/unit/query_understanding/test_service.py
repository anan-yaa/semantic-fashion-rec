"""Unit tests for app/services/query_understanding/service.py.

Covers: understand_query()'s success and fallback paths, validate_filters()'s
hard catalogue-vocabulary gate, and merge_filters()'s precedence rules.
"""
from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import QueryUnderstanding
from app.schemas.search import SearchFilter
from app.services.query_understanding.service import (
    merge_filters,
    understand_query,
    validate_filters,
)

VALID_FILTERS = {
    "category": ["Apparel", "Footwear"],
    "gender": ["Men", "Women"],
    "color": ["Black", "Blue"],
    "season": ["Summer", "Winter"],
}


class TestUnderstandQuery:
    def test_success_path_uses_llm_output(self):
        canned = QueryUnderstanding(
            cleaned_query="running shoes",
            filters=SearchFilter(category="Footwear"),
        )
        provider = FakeLLMProvider(canned_responses={"blue running shoes": canned})

        result = understand_query(provider, "blue running shoes", VALID_FILTERS)

        assert result.used_llm is True
        assert result.cleaned_query == "running shoes"
        assert result.filters.category == "Footwear"
        assert result.error is None

    def test_failure_path_falls_back_to_original_query_with_no_filters(self):
        provider = FakeLLMProvider(raise_error=True)

        result = understand_query(provider, "blue running shoes", VALID_FILTERS)

        assert result.used_llm is False
        assert result.cleaned_query == "blue running shoes"
        assert result.filters == SearchFilter()
        assert result.error is not None

    def test_failure_path_never_raises(self):
        provider = FakeLLMProvider(raise_error=True)

        # Must not raise.
        understand_query(provider, "anything", VALID_FILTERS)

    def test_out_of_vocabulary_llm_filter_is_dropped_before_being_returned(self):
        canned = QueryUnderstanding(
            cleaned_query="q",
            filters=SearchFilter(category="Electronics"),  # not a real catalogue value
        )
        provider = FakeLLMProvider(canned_responses={"q": canned})

        result = understand_query(provider, "q", VALID_FILTERS)

        assert result.filters.category is None


class TestValidateFilters:
    def test_valid_values_pass_through(self):
        raw = SearchFilter(category="Apparel", color="Black")

        validated = validate_filters(raw, VALID_FILTERS)

        assert validated.category == "Apparel"
        assert validated.color == "Black"

    def test_out_of_vocabulary_value_is_dropped(self):
        raw = SearchFilter(category="Electronics")

        validated = validate_filters(raw, VALID_FILTERS)

        assert validated.category is None

    def test_availability_is_never_populated_by_validate_filters(self):
        raw = SearchFilter(availability=True)

        validated = validate_filters(raw, VALID_FILTERS)

        assert validated.availability is None


class TestMergeFilters:
    def test_explicit_user_filter_wins_over_llm_inferred_one(self):
        user_filters = SearchFilter(gender="Men")
        llm_filters = SearchFilter(gender="Women", color="Blue")

        merged = merge_filters(user_filters, llm_filters)

        assert merged.gender == "Men"
        assert merged.color == "Blue"

    def test_llm_filter_used_when_user_did_not_specify_that_field(self):
        user_filters = SearchFilter()
        llm_filters = SearchFilter(category="Footwear")

        merged = merge_filters(user_filters, llm_filters)

        assert merged.category == "Footwear"

    def test_availability_always_sourced_from_user_only(self):
        user_filters = SearchFilter(availability=True)
        llm_filters = SearchFilter()

        merged = merge_filters(user_filters, llm_filters)

        assert merged.availability is True

    def test_none_user_filters_defaults_cleanly(self):
        llm_filters = SearchFilter(category="Apparel")

        merged = merge_filters(None, llm_filters)

        assert merged.category == "Apparel"
        assert merged.availability is None


class TestFallbackReason:
    def test_unsupported_query_is_reported_as_such(self):
        from app.providers.llm_base import UnsupportedQueryError

        class SkippingProvider(FakeLLMProvider):
            def understand_query(self, query, valid_filters):
                raise UnsupportedQueryError("skipped")

        result = understand_query(SkippingProvider(), "नीली शर्ट", VALID_FILTERS)

        assert result.used_llm is False
        assert result.cleaned_query == "नीली शर्ट"
        assert result.fallback_reason == "unsupported_query"

    def test_provider_failure_is_reported_as_unavailable(self):
        result = understand_query(FakeLLMProvider(raise_error=True), "q", VALID_FILTERS)

        assert result.fallback_reason == "llm_unavailable"

    def test_success_has_no_fallback_reason(self):
        result = understand_query(FakeLLMProvider(), "q", VALID_FILTERS)

        assert result.fallback_reason is None
