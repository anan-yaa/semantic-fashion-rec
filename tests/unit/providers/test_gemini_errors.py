"""GeminiProvider maps SDK/network errors to the right LLMProviderError subclass."""
from unittest.mock import MagicMock

import httpx
import pytest
from google.genai import errors as genai_errors

from app.providers.llm import GeminiProvider
from app.providers.llm_base import LLMProviderError, LLMRateLimitedError, LLMUnavailableError

VALID_FILTERS = {"category": ["Apparel"], "gender": ["Men"], "color": ["Black"], "season": ["Summer"]}


def _provider_raising(error):
    provider = GeminiProvider(api_key="test", model="m", timeout_seconds=1, max_retries=0)
    client = MagicMock()
    client.models.generate_content.side_effect = error
    provider._client = client
    return provider


def test_429_is_rate_limited():
    error = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(LLMRateLimitedError):
        _provider_raising(error).understand_query("q", VALID_FILTERS)


def test_server_error_is_unavailable():
    error = genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})
    with pytest.raises(LLMUnavailableError):
        _provider_raising(error).understand_query("q", VALID_FILTERS)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.ConnectError("refused")])
def test_network_errors_are_unavailable(error):
    with pytest.raises(LLMUnavailableError):
        _provider_raising(error).understand_query("q", VALID_FILTERS)


def test_other_client_errors_are_not_unavailable():
    error = genai_errors.ClientError(400, {"error": {"code": 400, "message": "bad request", "status": "INVALID_ARGUMENT"}})
    with pytest.raises(LLMProviderError) as info:
        _provider_raising(error).understand_query("q", VALID_FILTERS)
    assert not isinstance(info.value, LLMUnavailableError)
