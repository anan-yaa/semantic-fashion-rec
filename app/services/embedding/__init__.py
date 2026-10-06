"""Embedding generation and management."""
from app.services.embedding.service import EmbeddingStats, embed_products, get_unembedded_products

__all__ = ["EmbeddingStats", "embed_products", "get_unembedded_products"]
