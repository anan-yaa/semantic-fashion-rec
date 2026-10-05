"""Ollama-backed LLM provider for query understanding."""
import json
import logging
from typing import Dict, List, Optional

import requests

from app.providers.llm_base import LLMProvider, LLMProviderError, QueryUnderstanding
from app.schemas.search import SearchFilter

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You extract search intent from a single fashion-catalogue search query. "
    "Produce two things:\n"
    "1. cleaned_query: a short, keyword-dense rephrasing of the query, suitable "
    "for a literal keyword index. Strip filler words (e.g. 'for', 'a', 'that', "
    "'days') but keep every substantive descriptive word (colors, materials, "
    "occasions, item types).\n"
    "2. category/gender/color/season: only set a field when the query clearly "
    "and confidently implies one of the allowed values for it. Never guess - "
    "prefer null over a wrong value. Do not infer availability; it is not part "
    "of your job and cannot be inferred from text.\n"
    "Respond only with the requested JSON object."
)

_INFERABLE_FIELDS = ("category", "gender", "color", "season")


def _parse_model_output(raw: dict, valid_filters: Dict[str, List[str]]) -> QueryUnderstanding:
    """Parse and validate a decoded JSON response dict into a QueryUnderstanding."""
    cleaned_query = raw.get("cleaned_query")
    if not isinstance(cleaned_query, str) or not cleaned_query.strip():
        raise LLMProviderError(f"Ollama response missing a usable cleaned_query: {raw!r}")

    filters = SearchFilter()
    for field_name in _INFERABLE_FIELDS:
        value = raw.get(field_name)
        if value is None:
            continue
        if value in valid_filters.get(field_name, []):
            setattr(filters, field_name, value)
        else:
            logger.warning(f"Ollama returned out-of-vocabulary {field_name}={value!r}, dropping")

    return QueryUnderstanding(cleaned_query=cleaned_query.strip(), filters=filters)


class OllamaProvider(LLMProvider):
    """Ollama integration for local query understanding via orca-mini or similar."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 15.0,
    ):
        self._model = model
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    def understand_query(
        self, query: str, valid_filters: Dict[str, List[str]]
    ) -> QueryUnderstanding:
        """Call Ollama to extract cleaned query and filters."""
        prompt = f"""{_SYSTEM_PROMPT}

User query: {query}

Allowed values:
{json.dumps(valid_filters, indent=2)}

Respond only with valid JSON."""

        try:
            response = requests.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise LLMProviderError(f"Ollama request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMProviderError(f"Failed to connect to Ollama at {self._base_url}: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Ollama API call failed: {e}") from e

        try:
            data = response.json()
            text = data.get("response", "").strip()
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Ollama response was not valid JSON: {e}") from e

        if not text:
            raise LLMProviderError("Ollama response contained no text")

        # Extract JSON from response (it might be wrapped in text)
        try:
            # Try direct parse first
            raw = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            import re
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if not json_match:
                raise LLMProviderError(f"Ollama response contained no JSON object: {text}")
            try:
                raw = json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                raise LLMProviderError(f"Ollama response contained invalid JSON: {e}") from e

        return _parse_model_output(raw, valid_filters)
