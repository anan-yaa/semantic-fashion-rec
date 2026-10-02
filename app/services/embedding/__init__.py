"""Embedding generation and management."""
from app.services.embedding.service import embed_products, get_unembedded_products, EmbeddingStats

__all__ = ["embed_products", "get_unembedded_products", "EmbeddingStats"]
