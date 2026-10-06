#!/usr/bin/env python3
"""Sanity-check the real intfloat/multilingual-e5-base model.

Loads the actual model (no mocking) and verifies:
- Output dimension is 768
- Embeddings are L2-normalized
- query/passage prefix convention produces sensible similarity ordering
- Multilingual queries (Hindi) work

Run manually; this is NOT part of the regular test suite (downloads a ~1GB
model and is slow). Use tests/model/test_e5_real.py (pytest, marked slow) for
an automated equivalent.
"""
import logging
import sys

from app.providers.e5 import HuggingFaceE5Provider
from core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x**2 for x in a) ** 0.5
    mag_b = sum(y**2 for y in b) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def main() -> int:
    logger.info("Loading intfloat/multilingual-e5-base (this may take a while on first run)...")
    provider = HuggingFaceE5Provider()

    failures = []

    # 1. Dimension check
    passages = ["A blue cotton shirt for men", "A red summer dress for women", "Winter wool coat"]
    embeddings = provider.embed_passages(passages)

    for i, emb in enumerate(embeddings):
        if len(emb) != 768:
            failures.append(f"Passage {i}: expected dim 768, got {len(emb)}")
    logger.info(f"Dimension check: {len(embeddings[0])}-d vectors" if embeddings else "FAILED: no embeddings")

    # 2. Normalization check
    for i, emb in enumerate(embeddings):
        norm = sum(x**2 for x in emb) ** 0.5
        if abs(norm - 1.0) > 1e-3:
            failures.append(f"Passage {i}: not normalized, norm={norm:.4f}")
    logger.info("Normalization check: all vectors ~unit length" if not failures else "FAILED normalization")

    # 3. Query/passage relevance ordering
    query_emb = provider.embed_queries(["blue shirt"])[0]
    similarities = [cosine_similarity(query_emb, e) for e in embeddings]
    logger.info(f"Similarities to 'blue shirt': {[f'{s:.3f}' for s in similarities]}")

    best_match_idx = similarities.index(max(similarities))
    if best_match_idx != 0:
        failures.append(
            f"Expected passage 0 ('blue cotton shirt') to be most similar to query "
            f"'blue shirt', but passage {best_match_idx} scored higher"
        )
    else:
        logger.info("Relevance ordering check: PASSED (blue shirt query matched blue shirt passage)")

    # 4. Multilingual check (Hindi)
    hindi_passages = ["नीली सूती शर्ट पुरुषों के लिए", "सर्दियों का ऊनी कोट"]
    hindi_embeddings = provider.embed_passages(hindi_passages)
    hindi_query_emb = provider.embed_queries(["नीली शर्ट"])[0]  # "blue shirt" in Hindi
    hindi_sims = [cosine_similarity(hindi_query_emb, e) for e in hindi_embeddings]
    logger.info(f"Hindi similarities: {[f'{s:.3f}' for s in hindi_sims]}")

    if hindi_sims.index(max(hindi_sims)) != 0:
        failures.append("Hindi query did not match the semantically correct Hindi passage")
    else:
        logger.info("Multilingual check: PASSED (Hindi query matched correct Hindi passage)")

    # Summary
    if failures:
        logger.error(f"VERIFICATION FAILED ({len(failures)} issue(s)):")
        for f in failures:
            logger.error(f"  - {f}")
        return 1

    logger.info("All e5 model verification checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
