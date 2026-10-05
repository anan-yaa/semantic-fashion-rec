#!/usr/bin/env python3
"""Test script to verify Ollama provider works with orca-mini."""

import time
from app.providers.ollama_llm import OllamaProvider
from core.config import Settings

def test_ollama_extraction():
    """Test filter extraction with Ollama."""
    settings = Settings(
        llm_provider="ollama",
        ollama_model="orca-mini",
        llm_query_understanding_timeout_seconds=5.0,
    )

    provider = OllamaProvider(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.llm_query_understanding_timeout_seconds,
    )

    # Mock filter vocabulary from your catalogue
    valid_filters = {
        "category": ["Topwear", "Bottomwear", "Accessories"],
        "gender": ["Men", "Women", "Unisex"],
        "color": ["Black", "White", "Blue", "Red", "Green", "Brown"],
        "season": ["Summer", "Winter", "Fall", "Spring"],
    }

    test_queries = [
        "black leather jacket for men",
        "blue cotton shirt for women",
        "summer dresses",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)
        start = time.time()
        try:
            result = provider.understand_query(query, valid_filters)
            elapsed = time.time() - start
            print(f"✓ Success ({elapsed:.2f}s)")
            print(f"  Cleaned: {result.cleaned_query}")
            print(f"  Filters: {result.filters}")
        except Exception as e:
            elapsed = time.time() - start
            print(f"✗ Failed ({elapsed:.2f}s): {e}")

if __name__ == "__main__":
    print("Testing Ollama provider with orca-mini...")
    print("Make sure Ollama is running: ollama serve")
    print()
    test_ollama_extraction()
