"""Unit tests for OllamaProvider: request shape, parsing, grounding, and failure modes.

The HTTP call is mocked; no Ollama server is needed.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.providers.llm_base import LLMProviderError
from app.providers.ollama_llm import OllamaProvider, _parse_model_output

VALID_FILTERS = {
    "category": ["Apparel", "Footwear"],
    "gender": ["Men", "Women", "Boys", "Girls"],
    "color": ["Black", "Blue", "Navy Blue", "Red"],
    "season": ["Summer", "Winter", "Fall"],
}


def _raw(english_query="q", gender=None, color=None, season=None):
    return {"english_query": english_query, "gender": gender, "color": color, "season": season}


def _mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"message": {"content": content}}
    response.raise_for_status.return_value = None
    return response


class TestParseModelOutput:
    def test_grounded_filters_are_kept(self):
        raw = _raw("black leather jacket", gender="Men", color="Black")
        result = _parse_model_output(raw, VALID_FILTERS, "black leather jacket for men")
        assert result.cleaned_query == "black leather jacket"
        assert result.filters.gender == "Men"
        assert result.filters.color == "Black"

    def test_ungrounded_season_is_dropped(self):
        raw = _raw("woollen coat", season="Summer")
        result = _parse_model_output(raw, VALID_FILTERS, "warm woollen coat")
        assert result.filters.season is None

    def test_women_does_not_ground_men(self):
        raw = _raw("dress", gender="Men")
        result = _parse_model_output(raw, VALID_FILTERS, "dress for women")
        assert result.filters.gender is None

    def test_gender_synonyms_ground(self):
        assert _parse_model_output(_raw("kurta", gender="Women"), VALID_FILTERS, "ladies kurta").filters.gender == "Women"
        assert _parse_model_output(_raw("shirt", gender="Men"), VALID_FILTERS, "men's shirt").filters.gender == "Men"
        assert _parse_model_output(_raw("tee", gender="Boys"), VALID_FILTERS, "boys tee").filters.gender == "Boys"

    def test_autumn_grounds_fall(self):
        result = _parse_model_output(_raw("jacket", season="Fall"), VALID_FILTERS, "autumn jacket")
        assert result.filters.season == "Fall"

    def test_multi_word_color_needs_full_phrase(self):
        assert _parse_model_output(_raw("shirt", color="Navy Blue"), VALID_FILTERS, "navy blue shirt").filters.color == "Navy Blue"
        assert _parse_model_output(_raw("shirt", color="Navy Blue"), VALID_FILTERS, "blue shirt").filters.color is None

    def test_color_is_whole_word_match(self):
        result = _parse_model_output(_raw("shirt", color="Red"), VALID_FILTERS, "embroidered shirt")
        assert result.filters.color is None

    def test_out_of_vocabulary_value_is_dropped(self):
        result = _parse_model_output(_raw("purple shirt", color="Purple"), VALID_FILTERS, "purple shirt")
        assert result.filters.color is None

    def test_category_is_never_inferred(self):
        raw = {**_raw("red saree"), "category": "Footwear"}
        result = _parse_model_output(raw, VALID_FILTERS, "red saree")
        assert result.filters.category is None

    @pytest.mark.parametrize("cleaned", [None, "", "   ", 42])
    def test_unusable_cleaned_query_raises(self, cleaned):
        with pytest.raises(LLMProviderError):
            _parse_model_output(_raw(cleaned), VALID_FILTERS, "query")


class TestTranslation:
    def test_english_query_is_not_translated(self):
        result = _parse_model_output(_raw("red dress for women"), VALID_FILTERS, "red dress for women")
        assert result.translated is False

    def test_translated_query_is_grounded_in_english(self):
        raw = _raw("red dress for women", color="Red", gender="Women")
        result = _parse_model_output(raw, VALID_FILTERS, "vestido rojo para mujer", translated=True)
        assert result.translated is True
        assert result.cleaned_query == "red dress for women"
        assert (result.filters.color, result.filters.gender) == ("Red", "Women")

    @pytest.mark.parametrize(
        "query, label, translated",
        [
            ("black leather jacket for men", "English", False),
            ("vestido rojo para mujer", "Spanish", True),
            ("robe rouge pour femme", "French", True),
            ("नीली शर्ट", "Hindi", True),
        ],
    )
    def test_the_detected_language_is_given_to_the_model(self, query, label, translated):
        provider = OllamaProvider(model="gemma3:1b")
        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response(json.dumps(_raw("x")))) as post:
            result = provider.understand_query(query, VALID_FILTERS)
        assert post.call_args.kwargs["json"]["messages"][-1]["content"] == f"Query ({label}): {query}"
        assert result.translated is translated


class TestUnderstandQuery:
    def setup_method(self):
        self.provider = OllamaProvider(model="tinyllama", base_url="http://ollama:11434/", timeout_seconds=3)

    def test_sends_schema_constrained_chat_request(self):
        content = json.dumps(_raw("red dress", color="Red"))
        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response(content)) as post:
            result = self.provider.understand_query("red dress", VALID_FILTERS)

        assert result.filters.color == "Red"
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        assert url == "http://ollama:11434/api/chat"
        assert kwargs["timeout"] == 3
        payload = kwargs["json"]
        assert payload["model"] == "tinyllama"
        assert payload["options"]["temperature"] == 0
        assert payload["format"]["properties"]["color"]["enum"] == [*VALID_FILTERS["color"], None]
        assert "category" not in payload["format"]["properties"]
        assert "language" not in payload["format"]["properties"]
        assert next(iter(payload["format"]["properties"])) == "english_query"
        assert payload["messages"][-1]["content"] == "Query (English): red dress"

    def test_non_latin_query_is_sent_to_a_multilingual_model(self):
        content = json.dumps(_raw("blue shirt", color="Blue"))
        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response(content)) as post:
            result = self.provider.understand_query("नीली शर्ट", VALID_FILTERS)
        post.assert_called_once()
        # Grounded through the English translation, since the Hindi text has no English words.
        assert result.filters.color == "Blue"

    def test_non_latin_query_skips_an_english_only_model(self):
        from app.providers.llm_base import UnsupportedQueryError

        provider = OllamaProvider(model="tinyllama", skip_non_latin=True)
        with patch("app.providers.ollama_llm.requests.post") as post, pytest.raises(UnsupportedQueryError):
            provider.understand_query("नीली शर्ट", VALID_FILTERS)
        post.assert_not_called()

    def test_accented_latin_query_uses_the_model_even_when_skipping_non_latin(self):
        provider = OllamaProvider(model="tinyllama", skip_non_latin=True)
        content = json.dumps(_raw("robe rouge"))
        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response(content)) as post:
            provider.understand_query("robe rouge élégante", VALID_FILTERS)
        post.assert_called_once()

    @pytest.mark.parametrize(
        "error",
        [requests.exceptions.Timeout("slow"), requests.exceptions.ConnectionError("down"), requests.exceptions.HTTPError("500")],
    )
    def test_http_failures_raise_provider_error(self, error):
        with patch("app.providers.ollama_llm.requests.post", side_effect=error):
            with pytest.raises(LLMProviderError):
                self.provider.understand_query("red dress", VALID_FILTERS)

    @pytest.mark.parametrize("content", ["Extractions:", "[1, 2]", ""])
    def test_bad_model_output_raises_provider_error(self, content):
        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response(content)):
            with pytest.raises(LLMProviderError):
                self.provider.understand_query("red dress", VALID_FILTERS)

    def test_warm_up_failure_does_not_raise(self):
        with patch("app.providers.ollama_llm.requests.post", side_effect=requests.exceptions.ConnectionError("down")):
            self.provider.warm_up()


class TestErrorClassification:
    """Which failures count as 'Ollama is unavailable' for the circuit breaker."""

    def setup_method(self):
        self.provider = OllamaProvider(model="tinyllama", timeout_seconds=3)

    def _http_error(self, status):
        response = MagicMock(status_code=status)
        error = requests.exceptions.HTTPError(f"{status}", response=response)
        mocked = MagicMock()
        mocked.raise_for_status.side_effect = error
        return mocked

    @pytest.mark.parametrize(
        "error", [requests.exceptions.Timeout("slow"), requests.exceptions.ConnectionError("refused")]
    )
    def test_timeouts_and_connection_errors_are_unavailable(self, error):
        from app.providers.llm_base import LLMUnavailableError

        with patch("app.providers.ollama_llm.requests.post", side_effect=error):
            with pytest.raises(LLMUnavailableError):
                self.provider.understand_query("red dress", VALID_FILTERS)

    def test_server_error_is_unavailable(self):
        from app.providers.llm_base import LLMUnavailableError

        with patch("app.providers.ollama_llm.requests.post", return_value=self._http_error(503)):
            with pytest.raises(LLMUnavailableError):
                self.provider.understand_query("red dress", VALID_FILTERS)

    def test_client_error_is_not_unavailable(self):
        from app.providers.llm_base import LLMUnavailableError

        with patch("app.providers.ollama_llm.requests.post", return_value=self._http_error(404)):
            with pytest.raises(LLMProviderError) as info:
                self.provider.understand_query("red dress", VALID_FILTERS)
        assert not isinstance(info.value, LLMUnavailableError)

    def test_invalid_json_is_not_unavailable(self):
        from app.providers.llm_base import LLMUnavailableError

        with patch("app.providers.ollama_llm.requests.post", return_value=_mock_response("Extractions:")):
            with pytest.raises(LLMProviderError) as info:
                self.provider.understand_query("red dress", VALID_FILTERS)
        assert not isinstance(info.value, LLMUnavailableError)
