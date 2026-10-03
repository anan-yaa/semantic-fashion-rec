"""Unit tests for GeminiProvider's pure parse/validation helpers.

These take hand-crafted dicts (as if decoded from the model's JSON response
text) and need no network/SDK mocking - the point is proving a hallucinated
or malformed value from Gemini can never silently pass through as a usable
QueryUnderstanding, independent of the API's own structured-output schema
enforcement.
"""
import pytest

from app.providers.llm import _build_response_schema, _parse_model_output
from app.providers.llm_base import LLMProviderError

VALID_FILTERS = {
    "category": ["Apparel", "Footwear"],
    "gender": ["Men", "Women"],
    "color": ["Black", "Blue"],
    "season": ["Summer", "Winter"],
}


class TestParseModelOutput:
    def test_valid_response_parses_cleanly(self):
        raw = {
            "cleaned_query": "blue running shoes",
            "category": "Footwear",
            "gender": None,
            "color": "Blue",
            "season": None,
        }

        result = _parse_model_output(raw, VALID_FILTERS)

        assert result.cleaned_query == "blue running shoes"
        assert result.filters.category == "Footwear"
        assert result.filters.color == "Blue"
        assert result.filters.gender is None
        assert result.filters.season is None

    def test_hallucinated_out_of_vocabulary_value_is_dropped_not_passed_through(self):
        raw = {
            "cleaned_query": "electronics",
            "category": "Electronics",  # not in VALID_FILTERS["category"]
            "gender": None,
            "color": None,
            "season": None,
        }

        result = _parse_model_output(raw, VALID_FILTERS)

        assert result.filters.category is None

    def test_all_fields_hallucinated_are_all_dropped(self):
        raw = {
            "cleaned_query": "q",
            "category": "Nonsense",
            "gender": "Nonsense",
            "color": "Nonsense",
            "season": "Nonsense",
        }

        result = _parse_model_output(raw, VALID_FILTERS)

        assert result.filters.category is None
        assert result.filters.gender is None
        assert result.filters.color is None
        assert result.filters.season is None

    def test_missing_cleaned_query_raises(self):
        raw = {"category": None, "gender": None, "color": None, "season": None}

        with pytest.raises(LLMProviderError):
            _parse_model_output(raw, VALID_FILTERS)

    def test_empty_cleaned_query_raises(self):
        raw = {"cleaned_query": "   ", "category": None, "gender": None, "color": None, "season": None}

        with pytest.raises(LLMProviderError):
            _parse_model_output(raw, VALID_FILTERS)

    def test_cleaned_query_is_stripped(self):
        raw = {"cleaned_query": "  shoes  ", "category": None, "gender": None, "color": None, "season": None}

        result = _parse_model_output(raw, VALID_FILTERS)

        assert result.cleaned_query == "shoes"


class TestBuildResponseSchema:
    def test_schema_enums_are_built_from_the_live_vocabulary_passed_in(self):
        schema = _build_response_schema(VALID_FILTERS)

        props = schema["properties"]
        category_enum = next(b["enum"] for b in props["category"]["anyOf"] if "enum" in b)
        color_enum = next(b["enum"] for b in props["color"]["anyOf"] if "enum" in b)
        assert set(category_enum) == {"Apparel", "Footwear"}
        assert set(color_enum) == {"Black", "Blue"}

    def test_schema_fields_are_nullable_via_any_of(self):
        schema = _build_response_schema(VALID_FILTERS)

        types_present = {b.get("type") for b in schema["properties"]["gender"]["anyOf"]}
        assert "null" in types_present

    def test_schema_forbids_additional_properties_and_requires_all_fields(self):
        schema = _build_response_schema(VALID_FILTERS)

        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {
            "cleaned_query",
            "category",
            "gender",
            "color",
            "season",
        }
