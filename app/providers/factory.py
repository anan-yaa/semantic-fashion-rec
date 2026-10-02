"""Factory for creating embedding providers."""
import logging

from app.providers.base import EmbeddingProvider
from app.providers.e5 import HuggingFaceE5Provider
from app.providers.fake import FakeEmbeddingProvider
from core.config import Settings

logger = logging.getLogger(__name__)


def get_embedding_provider(settings: Settings, use_fake: bool = False) -> EmbeddingProvider:
    """Get an embedding provider based on settings.

    Args:
        settings: Application settings.
        use_fake: If True, return FakeEmbeddingProvider (for testing).

    Returns:
        An EmbeddingProvider instance.
    """
    if use_fake:
        logger.info("Using FakeEmbeddingProvider for testing")
        return FakeEmbeddingProvider()

    logger.info(f"Using HuggingFaceE5Provider: {settings.embedding_model}")
    return HuggingFaceE5Provider(
        model_name=settings.embedding_model,
        batch_size=settings.embedding_batch_size,
    )
