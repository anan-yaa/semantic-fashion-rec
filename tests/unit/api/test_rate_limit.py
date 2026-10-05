"""Unit tests for the token-bucket rate limiter (fake clock, no sleeping)."""
import pytest

from app.api.rate_limit import TokenBucketLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(rate_per_minute=30, burst=10, max_clients=10_000):
    clock = FakeClock()
    return TokenBucketLimiter(rate_per_minute, burst, clock=clock, max_clients=max_clients), clock


def test_burst_is_allowed_then_limited():
    limiter, _ = make(burst=10)
    assert all(limiter.acquire("ip") == 0 for _ in range(10))
    assert limiter.acquire("ip") > 0


def test_wait_time_matches_refill_rate():
    limiter, _ = make(rate_per_minute=30, burst=1)  # one token every 2 s
    limiter.acquire("ip")
    assert limiter.acquire("ip") == pytest.approx(2.0)


def test_tokens_refill_over_time():
    limiter, clock = make(rate_per_minute=30, burst=2)
    limiter.acquire("ip")
    limiter.acquire("ip")
    assert limiter.acquire("ip") > 0
    clock.now += 2.0
    assert limiter.acquire("ip") == 0
    assert limiter.acquire("ip") > 0


def test_refill_never_exceeds_burst():
    limiter, clock = make(rate_per_minute=60, burst=3)
    clock.now += 3600
    assert all(limiter.acquire("ip") == 0 for _ in range(3))
    assert limiter.acquire("ip") > 0


def test_rejected_requests_do_not_consume_tokens():
    limiter, clock = make(rate_per_minute=60, burst=1)
    limiter.acquire("ip")
    for _ in range(5):
        limiter.acquire("ip")  # hammering while limited
    clock.now += 1.0
    assert limiter.acquire("ip") == 0


def test_clients_are_independent():
    limiter, _ = make(burst=1)
    assert limiter.acquire("a") == 0
    assert limiter.acquire("a") > 0
    assert limiter.acquire("b") == 0


def test_idle_clients_are_dropped():
    limiter, clock = make(rate_per_minute=60, burst=1, max_clients=2)
    limiter.acquire("a")
    limiter.acquire("b")
    clock.now += 5  # a and b refilled: same as never seen
    limiter.acquire("c")
    assert limiter.client_count() == 1


def test_active_clients_are_kept():
    limiter, _ = make(rate_per_minute=60, burst=1, max_clients=2)
    for key in ("a", "b", "c"):
        limiter.acquire(key)
    assert limiter.client_count() == 3
    assert limiter.acquire("a") > 0


def test_reset():
    limiter, _ = make(burst=1)
    limiter.acquire("ip")
    limiter.reset()
    assert limiter.acquire("ip") == 0
