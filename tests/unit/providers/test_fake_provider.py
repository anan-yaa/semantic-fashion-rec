"""Tests for FakeEmbeddingProvider."""
import pytest

from app.providers.fake import FakeEmbeddingProvider


class TestFakeEmbeddingProvider:
    """Test suite for FakeEmbeddingProvider."""

    def test_dim(self):
        """Test dimension is 768."""
        provider = FakeEmbeddingProvider()
        assert provider.dim == 768

    def test_embed_passages_returns_768d_vectors(self):
        """Test passages are embedded as 768-dimensional vectors."""
        provider = FakeEmbeddingProvider()
        texts = ["This is a passage", "Another passage"]

        embeddings = provider.embed_passages(texts)

        assert len(embeddings) == 2
        for emb in embeddings:
            assert len(emb) == 768
            assert all(isinstance(v, float) for v in emb)

    def test_embed_queries_returns_768d_vectors(self):
        """Test queries are embedded as 768-dimensional vectors."""
        provider = FakeEmbeddingProvider()
        texts = ["What is this?", "Search query"]

        embeddings = provider.embed_queries(texts)

        assert len(embeddings) == 2
        for emb in embeddings:
            assert len(emb) == 768

    def test_deterministic_same_text_same_embedding(self):
        """Test that the same text always produces the same embedding."""
        provider = FakeEmbeddingProvider()
        text = "This text should be consistent"

        emb1 = provider.embed_passages([text])[0]
        emb2 = provider.embed_passages([text])[0]

        assert emb1 == emb2

    def test_different_text_different_embedding(self):
        """Test that different texts produce different embeddings."""
        provider = FakeEmbeddingProvider()

        emb1 = provider.embed_passages(["Text one"])[0]
        emb2 = provider.embed_passages(["Text two"])[0]

        assert emb1 != emb2

    def test_embeddings_normalized(self):
        """Test that embeddings are L2-normalized (unit length)."""
        provider = FakeEmbeddingProvider()
        embeddings = provider.embed_passages(["Test passage"])

        emb = embeddings[0]
        norm = sum(v**2 for v in emb) ** 0.5

        assert abs(norm - 1.0) < 1e-5

    def test_empty_text_list(self):
        """Test empty text list returns empty embeddings."""
        provider = FakeEmbeddingProvider()

        embeddings = provider.embed_passages([])

        assert embeddings == []

    def test_batch_consistency_with_single(self):
        """Test that batching produces same results as individual embedding."""
        provider = FakeEmbeddingProvider()
        texts = ["First", "Second", "Third"]

        batch_embeddings = provider.embed_passages(texts)
        individual_embeddings = [provider.embed_passages([t])[0] for t in texts]

        assert batch_embeddings == individual_embeddings
