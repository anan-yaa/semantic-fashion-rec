"""Factory for creating LLM query-understanding providers."""
import logging

from app.providers.fake_llm import FakeLLMProvider
from app.providers.llm_base import LLMProvider
from core.config import Settings

logger = logging.getLogger(__name__)


def get_llm_provider(settings: Settings, use_fake: bool = False, for_eval: bool = False) -> LLMProvider:
    """Get an LLM provider based on settings.

    Args:
        settings: Application settings.
        use_fake: If True, return FakeLLMProvider (for testing).
        for_eval: If True, use eval-path timeout/retries (looser budget).
                  Otherwise use request-path timeout/retries (tight budget).

    Returns:
        An LLMProvider instance.
    """
    if use_fake:
        logger.info("Using FakeLLMProvider for testing")
        return FakeLLMProvider()

    # Lazy import to avoid dependency on google.genai when not using real LLM
    from app.providers.llm import GeminiProvider

    if for_eval:
        timeout = settings.llm_query_understanding_eval_timeout_seconds
        retries = settings.llm_query_understanding_eval_max_retries
        logger.info(f"Using GeminiProvider (eval mode): {settings.gemini_model}, timeout={timeout}s, retries={retries}")
    else:
        timeout = settings.llm_query_understanding_timeout_seconds
        retries = settings.llm_query_understanding_max_retries
        logger.info(f"Using GeminiProvider (request mode): {settings.gemini_model}, timeout={timeout}s, retries={retries}")

    return GeminiProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=timeout,
        max_retries=retries,
    )
