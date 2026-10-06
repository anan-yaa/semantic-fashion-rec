"""Circuit breaker for LLM query understanding.

Without it, a hung or unreachable LLM makes every search wait the full LLM
timeout before falling back. States:

- closed: calls go through. `failure_threshold` consecutive availability
  failures (timeout, connection error, 5xx) open the circuit; a rate limit
  (429) opens it immediately. Any success resets the count, so one slow call
  (e.g. while the model loads) doesn't trip it.
- open: the LLM is skipped instantly for `cooldown_seconds`.
- half-open: after the cooldown exactly one request is let through as a
  probe while others keep skipping; its success closes the circuit, its
  failure opens it again.

Every request let through by `allow_request()` must end with exactly one of
`record_success()`, `record_failure()` or `release()`, or a half-open probe
would never finish.
"""
import logging
import threading
import time
from collections.abc import Callable
from enum import Enum

from core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int,
        cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def allow_request(self) -> bool:
        """True if this request may call the LLM."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                if self._clock() - self._opened_at < self._cooldown_seconds:
                    return False
                self._state = CircuitState.HALF_OPEN
                logger.info("LLM circuit breaker half-open: sending one probe request")
            if self._probe_in_flight:
                return False
            self._probe_in_flight = True
            return True

    def record_success(self) -> None:
        """The LLM service answered (even if the answer itself was unusable)."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.warning("LLM circuit breaker closed: LLM is responding again")
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._probe_in_flight = False

    def record_failure(self, immediate: bool = False) -> None:
        """The LLM service is unavailable. `immediate` opens the circuit at once (rate limits)."""
        with self._lock:
            self._consecutive_failures += 1
            self._probe_in_flight = False
            if (
                immediate
                or self._state == CircuitState.HALF_OPEN
                or self._consecutive_failures >= self._failure_threshold
            ):
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        f"LLM circuit breaker opened after {self._consecutive_failures} consecutive "
                        f"failure(s): skipping the LLM for {self._cooldown_seconds:g}s"
                    )
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()

    def release(self) -> None:
        """The request ended without telling us anything about availability."""
        with self._lock:
            self._probe_in_flight = False

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = 0.0
            self._probe_in_flight = False


llm_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.llm_circuit_failure_threshold,
    cooldown_seconds=settings.llm_circuit_cooldown_seconds,
)
