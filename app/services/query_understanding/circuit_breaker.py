"""Circuit breaker for LLM query understanding.

Disables the LLM for a cooldown period after rate limits (429) or repeated
failures to prevent burning quota and keeping search responsive.
"""
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level state (thread-safe)
_lock = threading.Lock()
_last_failure_time: Optional[float] = None
_failure_count = 0
_cooldown_seconds = 60  # After a 429, skip the LLM for 60 seconds


def record_failure() -> None:
    """Record an LLM failure (429 or error). Triggers cooldown if threshold reached."""
    global _last_failure_time, _failure_count
    with _lock:
        _last_failure_time = time.time()
        _failure_count += 1
        if _failure_count >= 3:
            logger.warning(f"LLM circuit breaker: {_failure_count} failures in cooldown, disabling for {_cooldown_seconds}s")


def should_skip_llm() -> bool:
    """Check if the LLM should be skipped due to recent failures."""
    global _last_failure_time, _failure_count
    with _lock:
        if _last_failure_time is None:
            return False
        elapsed = time.time() - _last_failure_time
        if elapsed < _cooldown_seconds:
            logger.debug(f"LLM circuit breaker: skipping (cooldown {_cooldown_seconds - elapsed:.0f}s remaining)")
            return True
        # Cooldown expired, reset state
        _last_failure_time = None
        _failure_count = 0
        return False


def reset_for_testing() -> None:
    """Test hook to reset circuit breaker state."""
    global _last_failure_time, _failure_count
    with _lock:
        _last_failure_time = None
        _failure_count = 0
