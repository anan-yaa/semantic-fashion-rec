#!/usr/bin/env python3
"""Smoke-test the configured Ollama model against a running Ollama server.

Usage:
    PYTHONPATH=. python3 scripts/test_ollama_provider.py ["query" ...]
"""
import sys
import time

from app.db.database import get_session
from app.providers.llm_base import LLMProviderError
from app.providers.ollama_llm import OllamaProvider
from app.services.query_understanding import load_catalogue_facets
from core.config import settings

DEFAULT_QUERIES = [
    "black leather jacket for men",
    "I need an outfit to go to the beach this summer",
    "cozy winter outfit",
    "navy blue shirt",
    "नीली शर्ट",
]


def main() -> int:
    queries = sys.argv[1:] or DEFAULT_QUERIES
    provider = OllamaProvider(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.llm_query_understanding_timeout_seconds,
    )
    print(f"Model: {settings.ollama_model} at {settings.ollama_base_url}")
    session = next(get_session())
    try:
        facets = load_catalogue_facets(session)
    finally:
        session.close()

    start = time.time()
    provider.warm_up()
    print(f"Warm-up: {time.time() - start:.1f}s\n")

    used = 0
    for query in queries:
        start = time.time()
        try:
            result = provider.understand_query(query, facets)
            used += 1
            filters = {k: v for k, v in result.filters.model_dump().items() if v is not None}
            print(f"{time.time() - start:5.1f}s  LLM       {query!r} -> {result.cleaned_query!r} {filters}")
        except LLMProviderError as e:
            print(f"{time.time() - start:5.1f}s  FALLBACK  {query!r} -> {e}")

    print(f"\nLLM used for {used}/{len(queries)} queries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
