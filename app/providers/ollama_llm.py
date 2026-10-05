"""Ollama-backed LLM provider for query understanding (local models such as tinyllama)."""
import json
import logging
import re
from typing import Dict, List

import requests

from app.providers.llm_base import LLMProvider, LLMProviderError, QueryUnderstanding
from app.schemas.search import SearchFilter

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
_SYSTEM_PROMPT = """You turn a fashion shop search query into JSON.
cleaned_query: the important keywords (item, color, material, occasion, place).
gender, color, season: set only if the query clearly says so, otherwise null.

Query: black leather jacket for men
{"cleaned_query": "black leather jacket", "gender": "Men", "color": "Black", "season": null}

Query: I need an outfit to go to the beach this summer
{"cleaned_query": "beach summer outfit", "gender": null, "color": null, "season": "Summer"}

Query: comfortable running shoes for women
{"cleaned_query": "comfortable running shoes", "gender": "Women", "color": null, "season": null}"""


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


def _build_format_schema(valid_filters: Dict[str, List[str]]) -> dict:
    properties: dict = {"cleaned_query": {"type": "string"}}
    for field_name in _INFERABLE_FIELDS:
        properties[field_name] = {
            "type": ["string", "null"],
            "enum": [*valid_filters.get(field_name, []), None],
        }
    return {
        "type": "object",
        "properties": properties,
        "required": ["cleaned_query", *_INFERABLE_FIELDS],
    }


def _parse_model_output(
    raw: dict, valid_filters: Dict[str, List[str]], query: str
) -> QueryUnderstanding:
    cleaned_query = raw.get("cleaned_query")
    if not isinstance(cleaned_query, str) or not cleaned_query.strip():
        raise LLMProviderError(f"Ollama response missing a usable cleaned_query: {raw!r}")
    cleaned_query = cleaned_query.strip()

    # Ground against the cleaned query too, so translated non-English queries
    # ("नीली शर्ट" -> "blue shirt") can still yield filters.
    text = f"{query} {cleaned_query}".lower()
    filters = SearchFilter()
    for field_name in _INFERABLE_FIELDS:
        value = raw.get(field_name)
        if value is None or value not in valid_filters.get(field_name, []):
            continue
        if _is_grounded(field_name, value, text):
            setattr(filters, field_name, value)
        else:
            logger.info(f"Dropping ungrounded {field_name}={value!r} for query {query!r}")

    return QueryUnderstanding(cleaned_query=cleaned_query, filters=filters)


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
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._keep_alive = keep_alive

    def understand_query(
        self, query: str, valid_filters: Dict[str, List[str]]
    ) -> QueryUnderstanding:
        # Small local models mistranslate non-Latin scripts into unrelated
        # products (Hindi "jewellery for women" -> "running shoes"). Falling
        # back leaves these to multilingual-e5 vector search, which handles them.
        if _has_non_latin_letters(query):
            raise LLMProviderError("Non-Latin-script query skipped by local model; using raw query")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Query: {query}"},
            ],
            "format": _build_format_schema(valid_filters),
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"temperature": 0, "num_predict": 96},
        }

        try:
            response = requests.post(
                f"{self._base_url}/api/chat", json=payload, timeout=self._timeout_seconds
            )
            response.raise_for_status()
            text = response.json()["message"]["content"]
        except requests.exceptions.Timeout as e:
            raise LLMProviderError(f"Ollama request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMProviderError(f"Failed to connect to Ollama at {self._base_url}: {e}") from e
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            raise LLMProviderError(f"Ollama API call failed: {e}") from e

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Ollama response was not valid JSON: {e}: {text[:200]!r}") from e
        if not isinstance(raw, dict):
            raise LLMProviderError(f"Ollama response was not a JSON object: {text[:200]!r}")

        return _parse_model_output(raw, valid_filters, query)

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
