"""Factory for creating LLM query-understanding providers."""
import logging

from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm import GeminiProvider
from app.providers.llm_base import LLMProvider
from core.config import Settings

logger = logging.getLogger(__name__)


def get_llm_provider(settings: Settings, use_fake: bool = False) -> LLMProvider:
    """Get an LLM provider based on settings.

    Args:
        settings: Application settings.
        use_fake: If True, return FakeLLMProvider (for testing).

    Returns:
        An LLMProvider instance.
    """
    if use_fake:
        logger.info("Using FakeLLMProvider for testing")
        return FakeLLMProvider()

    logger.info(f"Using GeminiProvider: {settings.gemini_model}")
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.llm_query_understanding_timeout_seconds,
        max_retries=settings.llm_query_understanding_max_retries,
    )
