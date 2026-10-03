#!/usr/bin/env python3
"""Sanity-check the real Gemini query-understanding integration.

Calls the actual Gemini API (no mocking) on a handful of hand-picked queries
pulled from evals/queries/query_set_v1.json, spanning a few category tags,
and prints the extracted cleaned_query/filters for manual eyeballing.

Run manually; this is NOT part of the regular test suite (makes real,
billed API calls). Requires GEMINI_API_KEY to be set.
"""
import json
import logging
import sys

from core.config import settings
from core.logging import setup_logging
from app.providers.llm import GeminiProvider
from app.services.query_understanding.vocabulary import CATALOGUE_FACETS

setup_logging()
logger = logging.getLogger(__name__)

QUERY_SET_PATH = "evals/queries/query_set_v1.json"
SAMPLE_QUERY_IDS = {"q002", "q020", "q045"}  # keyword_heavy, semantic, occasion


def _load_sample_queries() -> list[str]:
    with open(QUERY_SET_PATH) as f:
        data = json.load(f)
    return [q["query"] for q in data["queries"] if q["id"] in SAMPLE_QUERY_IDS]


def main() -> int:
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY is not set - cannot verify the real Gemini provider.")
        return 1

    provider = GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.llm_query_understanding_timeout_seconds,
        max_retries=settings.llm_query_understanding_max_retries,
    )

    queries = _load_sample_queries()
    failures = []

    for query in queries:
        logger.info(f"Query: {query!r}")
        result = provider.understand_query(query, CATALOGUE_FACETS)
        logger.info(f"  cleaned_query: {result.cleaned_query!r}")
        logger.info(f"  filters: {result.filters}")

        if not result.cleaned_query.strip():
            failures.append(f"{query!r}: cleaned_query was empty")

        for field_name, allowed_values in CATALOGUE_FACETS.items():
            value = getattr(result.filters, field_name)
            if value is not None and value not in allowed_values:
                failures.append(f"{query!r}: out-of-vocab {field_name}={value!r}")

    if failures:
        logger.error(f"VERIFICATION FAILED ({len(failures)} issue(s)):")
        for f in failures:
            logger.error(f"  - {f}")
        return 1

    logger.info("All LLM provider verification checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
