"""Per-client rate limiting for expensive endpoints.

Token bucket per client: each client starts with `burst` tokens, each request
takes one, and tokens refill at `rate_per_minute`. A person can click around
in quick bursts, but nobody can sustain more than the refill rate. State is
in memory, per process.
"""
import math
import threading
import time
from typing import Callable, Dict, Tuple

from fastapi import HTTPException, Request, status

from core.config import settings


class TokenBucketLimiter:
    def __init__(
        self,
        rate_per_minute: float,
        burst: int,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = 10_000,
    ):
        self._rate = rate_per_minute / 60.0  # tokens per second
        self._burst = float(burst)
        self._clock = clock
        self._max_clients = max_clients
        self._lock = threading.Lock()
        self._buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, updated_at)

    def acquire(self, key: str) -> float:
        """Take a token for `key`. Returns 0 if allowed, else seconds until a token is available."""
        with self._lock:
            now = self._clock()
            tokens, updated_at = self._buckets.get(key, (self._burst, now))
            tokens = min(self._burst, tokens + (now - updated_at) * self._rate)
            if tokens >= 1:
                self._buckets[key] = (tokens - 1, now)
                if len(self._buckets) > self._max_clients:
                    self._drop_idle(now)
                return 0.0
            self._buckets[key] = (tokens, now)
            return (1 - tokens) / self._rate

    def _drop_idle(self, now: float) -> None:
        """Forget clients whose bucket has refilled completely: same as never seen."""
        self._buckets = {
            key: (tokens, updated_at)
            for key, (tokens, updated_at) in self._buckets.items()
            if tokens + (now - updated_at) * self._rate < self._burst
        }

    def client_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


search_rate_limiter = TokenBucketLimiter(
    rate_per_minute=settings.search_rate_limit_per_minute,
    burst=settings.search_rate_limit_burst,
)


def client_key(request: Request) -> str:
    """The client's IP address.

    Behind a reverse proxy every request comes from the proxy, so the real
    client is read from X-Forwarded-For - but only when explicitly trusted,
    since clients can send that header themselves to dodge the limit. The
    last entry is the one the (single, trusted) proxy appended.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def limit_search_rate(request: Request) -> None:
    """FastAPI dependency: 429 with Retry-After when a client searches too fast."""
    if not settings.rate_limit_enabled:
        return
    wait_seconds = search_rate_limiter.acquire(client_key(request))
    if wait_seconds > 0:
        retry_after = max(1, math.ceil(wait_seconds))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many searches. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
