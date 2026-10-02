"""Opt-in tests that load the REAL intfloat/multilingual-e5-base model.

These are marked `slow` and excluded from the default test run (see
pytest.ini: `addopts = ... -m "not slow"`). Run explicitly with:

    pytest tests/model/test_e5_real.py -m slow

Requires torch + sentence-transformers installed and downloads the model
(~1GB) on first run. Not suitable for CI on every commit; intended as a
periodic/manual sanity check that the real model still behaves as expected,
complementing scripts/verify_e5_model.py.
"""
import pytest

pytest.importorskip("torch")
pytest.importorskip("sentence_transformers")

from app.providers.e5 import HuggingFaceE5Provider


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x**2 for x in a) ** 0.5
    mag_b = sum(y**2 for y in b) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


@pytest.mark.slow
class TestE5RealModel:
    """Sanity checks against the real e5 model (not mocked, not faked)."""

    @pytest.fixture(scope="class")
    def provider(self):
        return HuggingFaceE5Provider()

    def test_output_dimension_is_768(self, provider):
        """Test the real model produces 768-dimensional embeddings."""
        embeddings = provider.embed_passages(["A blue cotton shirt"])
        assert len(embeddings[0]) == 768

    def test_embeddings_are_normalized(self, provider):
        """Test the real model's output vectors are L2-normalized."""
        embeddings = provider.embed_passages(["A blue cotton shirt", "A red summer dress"])
        for emb in embeddings:
            norm = sum(x**2 for x in emb) ** 0.5
            assert abs(norm - 1.0) < 1e-3

    def test_relevant_passage_ranks_highest(self, provider):
        """Test that a semantically relevant passage outranks an irrelevant one."""
        passages = [
            "A blue cotton shirt for men",
            "Winter wool coat for cold weather",
        ]
        embeddings = provider.embed_passages(passages)
        query_emb = provider.embed_queries(["blue shirt"])[0]

        similarities = [cosine_similarity(query_emb, e) for e in embeddings]
        assert similarities[0] > similarities[1]

    def test_multilingual_hindi_query_matches_hindi_passage(self, provider):
        """Test Hindi query/passage pairs rank correctly (multilingual support)."""
        passages = [
            "नीली सूती शर्ट पुरुषों के लिए",  # blue cotton shirt for men
            "सर्दियों का ऊनी कोट",  # winter wool coat
        ]
        embeddings = provider.embed_passages(passages)
        query_emb = provider.embed_queries(["नीली शर्ट"])[0]  # blue shirt

        similarities = [cosine_similarity(query_emb, e) for e in embeddings]
        assert similarities[0] > similarities[1]

    def test_batch_size_64_processes_without_error(self, provider):
        """Test a realistic batch size (matching config default) processes cleanly."""
        texts = [f"Product description number {i}" for i in range(64)]
        embeddings = provider.embed_passages(texts)
        assert len(embeddings) == 64
