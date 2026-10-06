"""Ollama-backed LLM provider for query understanding (local models such as tinyllama)."""
import json
import logging
import re

import requests

from app.providers.llm_base import (
    LLMProvider,
    LLMProviderError,
    LLMUnavailableError,
    QueryUnderstanding,
    UnsupportedQueryError,
)
from app.schemas.search import SearchFilter
from app.services.query_understanding.language import ENGLISH, detect_language

logger = logging.getLogger(__name__)

# Category is deliberately not inferred: small models guess it wrongly (e.g.
# "saree" -> Footwear) and, unlike the fields below, it can't be checked
# against the query's own words.
_INFERABLE_FIELDS = ("gender", "color", "season")

_GENDER_WORDS = {
    "Men": r"men|man|male|mens|men's|gents?|gentlemen",
    "Women": r"women|woman|female|womens|women's|ladies|lady",
    "Boys": r"boys?|boy's",
    "Girls": r"girls?|girl's",
}
_SEASON_WORDS = {"Fall": r"fall|autumn"}

# Small models follow examples far better than instructions, and the allowed
# values are enforced by the JSON schema, so the prompt stays short.
_SYSTEM_PROMPT = """You turn a fashion shop search query into JSON. The shop's catalogue is in English.
Each query comes labelled with its language.
english_query: the query in English. Translate it if the language is not English; copy English queries unchanged.
gender, color, season: set only if the query clearly says so, otherwise null.

Query (English): black leather jacket for men
{"english_query": "black leather jacket for men", "gender": "Men", "color": "Black", "season": null}

Query (English): I need an outfit to go to the beach this summer
{"english_query": "I need an outfit to go to the beach this summer", "gender": null, "color": null, "season": "Summer"}

Query (Hindi): हरी कुर्ती
{"english_query": "green kurti", "gender": null, "color": "Green", "season": null}

Query (Spanish): pantalones cortos azules para niño
{"english_query": "blue shorts for boys", "gender": "Boys", "color": "Blue", "season": null}"""


def _has_non_latin_letters(text: str) -> bool:
    return any(c.isalpha() and ord(c) > 0x024F for c in text)


def _is_grounded(field_name: str, value: str, text: str) -> bool:
    """True if the inferred value is actually mentioned in the query text."""
    if field_name == "gender":
        pattern = _GENDER_WORDS.get(value, re.escape(value.lower()))
    elif field_name == "season":
        pattern = _SEASON_WORDS.get(value, re.escape(value.lower()))
    else:
        pattern = re.escape(value.lower())
    return re.search(rf"\b(?:{pattern})\b", text) is not None


def _build_format_schema(valid_filters: dict[str, list[str]]) -> dict:
    properties: dict = {"english_query": {"type": "string"}}
    for field_name in _INFERABLE_FIELDS:
        properties[field_name] = {
            "type": ["string", "null"],
            "enum": [*valid_filters.get(field_name, []), None],
        }
    return {
        "type": "object",
        "properties": properties,
        "required": ["english_query", *_INFERABLE_FIELDS],
    }


def _parse_model_output(
    raw: dict, valid_filters: dict[str, list[str]], query: str, translated: bool = False
) -> QueryUnderstanding:
    english = raw.get("english_query")
    if not isinstance(english, str) or not english.strip():
        raise LLMProviderError(f"Ollama response missing a usable english_query: {raw!r}")
    english = english.strip()

    # Ground against the English text too, so translated queries
    # ("नीली शर्ट" -> "blue shirt") can still yield filters.
    text = f"{query} {english}".lower()
    filters = SearchFilter()
    for field_name in _INFERABLE_FIELDS:
        value = raw.get(field_name)
        if value is None or value not in valid_filters.get(field_name, []):
            continue
        if _is_grounded(field_name, value, text):
            setattr(filters, field_name, value)
        else:
            logger.info(f"Dropping ungrounded {field_name}={value!r} for query {query!r}")

    return QueryUnderstanding(cleaned_query=english, filters=filters, translated=translated)


class OllamaProvider(LLMProvider):
    """Local query understanding via an Ollama server.

    Constructing this does no I/O; connection errors surface as
    LLMProviderError on the first call, like GeminiProvider.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 15.0,
        keep_alive: str = "30m",
        skip_non_latin: bool = False,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._keep_alive = keep_alive
        self._skip_non_latin = skip_non_latin

    def understand_query(
        self, query: str, valid_filters: dict[str, list[str]]
    ) -> QueryUnderstanding:
        # English-only models (e.g. tinyllama) mistranslate non-Latin scripts
        # into unrelated products (Hindi "jewellery for women" -> "running
        # shoes"). Skipping leaves these to multilingual-e5 vector search.
        if self._skip_non_latin and _has_non_latin_letters(query):
            raise UnsupportedQueryError("Non-Latin-script query skipped by local model; using raw query")

        # The code, not the model, decides the language: small models can't
        # reliably tell Spanish or French from English (see language.py).
        language = detect_language(query)
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Query ({language}): {query}"},
            ],
            "format": _build_format_schema(valid_filters),
            "stream": False,
            "keep_alive": self._keep_alive,
            # Room for the full query repeated in English plus the filters
            "options": {"temperature": 0, "num_predict": 192},
        }

        try:
            response = requests.post(
                f"{self._base_url}/api/chat", json=payload, timeout=self._timeout_seconds
            )
            response.raise_for_status()
            text = response.json()["message"]["content"]
        except requests.exceptions.Timeout as e:
            raise LLMUnavailableError(f"Ollama request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMUnavailableError(f"Failed to connect to Ollama at {self._base_url}: {e}") from e
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and status >= 500:
                raise LLMUnavailableError(f"Ollama server error {status}: {e}") from e
            # 4xx (e.g. model not pulled) fails fast every time; not an outage.
            raise LLMProviderError(f"Ollama API call failed: {e}") from e
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            raise LLMProviderError(f"Ollama API call failed: {e}") from e

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Ollama response was not valid JSON: {e}: {text[:200]!r}") from e
        if not isinstance(raw, dict):
            raise LLMProviderError(f"Ollama response was not a JSON object: {text[:200]!r}")

        return _parse_model_output(raw, valid_filters, query, translated=language != ENGLISH)

    def warm_up(self) -> None:
        """Load the model into memory so the first real request doesn't pay the load time."""
        try:
            requests.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "keep_alive": self._keep_alive},
                timeout=120,
            ).raise_for_status()
            logger.info(f"Ollama model {self._model} loaded")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama warm-up failed (searches will fall back until it is reachable): {e}")
