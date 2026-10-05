"""Gemini-backed LLM provider for query understanding."""
import json
import logging
from typing import Dict, List, Optional

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.providers.llm_base import (
    LLMProvider,
    LLMProviderError,
    LLMRateLimitedError,
    LLMUnavailableError,
    QueryUnderstanding,
)
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


def _enum_or_null(values: List[str]) -> dict:
    return {"anyOf": [{"type": "string", "enum": values}, {"type": "null"}]}


def _build_response_schema(valid_filters: Dict[str, List[str]]) -> dict:
    """Build the structured-output JSON schema, constraining each facet
    field's enum to the live catalogue vocabulary passed in (never hardcoded).
    """
    properties = {
        "cleaned_query": {
            "type": "string",
            "description": "Short, keyword-dense rephrasing of the query for a literal keyword index.",
        }
    }
    for field_name in _INFERABLE_FIELDS:
        schema = _enum_or_null(valid_filters.get(field_name, []))
        schema["description"] = f"The catalogue {field_name} this query implies, or null if not clearly implied."
        properties[field_name] = schema

    return {
        "type": "object",
        "properties": properties,
        "required": ["cleaned_query", *_INFERABLE_FIELDS],
        "additionalProperties": False,
    }


def _parse_model_output(raw: dict, valid_filters: Dict[str, List[str]]) -> QueryUnderstanding:
    """Parse and validate a decoded JSON response dict into a QueryUnderstanding.

    Pure function, no network calls - this is the belt-and-suspenders
    revalidation layer on top of the schema's own enum constraints. Any
    facet value not present in valid_filters is dropped (coerced to None)
    rather than passed through, and a missing/empty cleaned_query raises
    rather than silently fabricating one.
    """
    cleaned_query = raw.get("cleaned_query")
    if not isinstance(cleaned_query, str) or not cleaned_query.strip():
        raise LLMProviderError(f"Gemini response missing a usable cleaned_query: {raw!r}")

    filters = SearchFilter()
    for field_name in _INFERABLE_FIELDS:
        value = raw.get(field_name)
        if value is None:
            continue
        if value in valid_filters.get(field_name, []):
            setattr(filters, field_name, value)
        else:
            logger.warning(f"Gemini returned out-of-vocabulary {field_name}={value!r}, dropping")

    return QueryUnderstanding(cleaned_query=cleaned_query.strip(), filters=filters)


class GeminiProvider(LLMProvider):
    """Real Gemini integration for query understanding.

    Constructing this provider does no I/O (no client validation call) so
    that the process-wide singleton dependency can never itself throw - a
    bad/missing API key only ever surfaces as an LLMProviderError from the
    first real call, caught by app/services/query_understanding/service.py.
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: str,
        timeout_seconds: float,
        max_retries: int,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def understand_query(
        self, query: str, valid_filters: Dict[str, List[str]]
    ) -> QueryUnderstanding:
        schema = _build_response_schema(valid_filters)
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=schema,
            max_output_tokens=512,
            http_options=types.HttpOptions(
                timeout=int(self._timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=self._max_retries + 1),
            ),
        )

        try:
            response = self._get_client().models.generate_content(
                model=self._model,
                contents=query,
                config=config,
            )
        except genai_errors.ClientError as e:
            if e.code == 429:
                raise LLMRateLimitedError(f"Rate limited (429): {e}") from e
            raise LLMProviderError(f"Gemini API call failed: {e}") from e
        except genai_errors.ServerError as e:
            raise LLMUnavailableError(f"Gemini server error {e.code}: {e}") from e
        except httpx.TransportError as e:
            # Timeouts and connection failures
            raise LLMUnavailableError(f"Gemini API unreachable: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"Gemini API call failed: {e}") from e

        text = response.text
        if not text:
            raise LLMProviderError("Gemini response contained no text")

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Gemini response was not valid JSON: {e}") from e

        return _parse_model_output(raw, valid_filters)
