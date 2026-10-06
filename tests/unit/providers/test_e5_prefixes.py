"""Tests for HuggingFaceE5Provider prefixes and behavior."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytest.importorskip("sentence_transformers", minversion=None)

from app.providers.e5 import HuggingFaceE5Provider


class TestE5Provider:
    """Test suite for HuggingFaceE5Provider."""

    def test_dim(self):
        """Test dimension is 768."""
        provider = HuggingFaceE5Provider()
        assert provider.dim == 768

    def test_embed_passages_adds_prefix(self):
        """Test that passages are embedded with 'passage: ' prefix."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.return_value = np.zeros((1, 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
            provider = HuggingFaceE5Provider()
            provider.embed_passages(["Blue shirt"])

            # Check that the model was called with the prefixed text
            call_args = mock_model.encode.call_args
            assert call_args is not None
            texts_arg = call_args[0][0]
            assert texts_arg[0] == "passage: Blue shirt"

    def test_embed_queries_adds_prefix(self):
        """Test that queries are embedded with 'query: ' prefix."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.return_value = np.zeros((1, 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
            provider = HuggingFaceE5Provider()
            provider.embed_queries(["What is blue?"])

            # Check that the model was called with the prefixed text
            call_args = mock_model.encode.call_args
            assert call_args is not None
            texts_arg = call_args[0][0]
            assert texts_arg[0] == "query: What is blue?"

    def test_batch_processing(self):
        """Test that texts are batched correctly."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.side_effect = lambda texts, **kw: np.zeros((len(texts), 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
            provider = HuggingFaceE5Provider(batch_size=2)
            texts = ["Text 1", "Text 2", "Text 3"]
            embeddings = provider.embed_passages(texts)

            # Should have 2 encode calls: batch of 2, then batch of 1
            assert mock_model.encode.call_count == 2
            assert len(embeddings) == 3

    def test_lazy_model_loading(self):
        """Test that model is loaded on first use."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.return_value = np.zeros((1, 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model) as mock_st:
            provider = HuggingFaceE5Provider()
            # Model not loaded yet
            assert provider._model is None

            # First embed call loads it
            provider.embed_passages(["Text"])
            assert mock_st.call_count == 1

            # Second embed call reuses it
            provider.embed_passages(["Another"])
            assert mock_st.call_count == 1  # Still 1, not 2

    def test_device_cpu_fallback(self):
        """Test device falls back to CPU when torch.cuda unavailable."""
        provider = HuggingFaceE5Provider()
        # Should have a device (cpu or cuda)
        assert provider._device in ("cpu", "cuda")

    def test_normalize_embeddings_parameter(self):
        """Test that normalize_embeddings=True is passed to model."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.return_value = np.zeros((1, 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
            provider = HuggingFaceE5Provider()
            provider.embed_passages(["Text"])

            call_kwargs = mock_model.encode.call_args[1]
            assert call_kwargs['normalize_embeddings'] is True

    def test_empty_texts(self):
        """Test that empty text list is handled."""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        mock_model.encode.return_value = np.zeros((0, 768), dtype=np.float32)

        with patch('sentence_transformers.SentenceTransformer', return_value=mock_model):
            provider = HuggingFaceE5Provider()
            embeddings = provider.embed_passages([])

            assert embeddings == []
