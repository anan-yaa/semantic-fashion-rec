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

    timeout = settings.llm_query_understanding_eval_timeout_seconds if for_eval else settings.llm_query_understanding_timeout_seconds
    retries = settings.llm_query_understanding_eval_max_retries if for_eval else settings.llm_query_understanding_max_retries

    if settings.llm_provider == "ollama":
        from app.providers.ollama_llm import OllamaProvider
        logger.info(f"Using OllamaProvider: {settings.ollama_model} at {settings.ollama_base_url}, timeout={timeout}s")
        return OllamaProvider(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout_seconds=timeout,
        )
    else:
        from app.providers.llm import GeminiProvider
        mode = "eval" if for_eval else "request"
        logger.info(f"Using GeminiProvider ({mode} mode): {settings.gemini_model}, timeout={timeout}s, retries={retries}")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=timeout,
            max_retries=retries,
        )
