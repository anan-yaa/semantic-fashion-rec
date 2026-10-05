"""Unit tests for the LLM circuit breaker (fake clock, no sleeping)."""
import threading

from app.services.query_understanding.circuit_breaker import CircuitBreaker, CircuitState


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(threshold=3, cooldown=30):
    clock = FakeClock()
    return CircuitBreaker(failure_threshold=threshold, cooldown_seconds=cooldown, clock=clock), clock


def fail(breaker, times=1, immediate=False):
    for _ in range(times):
        assert breaker.allow_request()
        breaker.record_failure(immediate=immediate)


class TestClosed:
    def test_starts_closed_and_allows_requests(self):
        breaker, _ = make()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request()

    def test_stays_closed_below_threshold(self):
        breaker, _ = make()
        fail(breaker, 2)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request()

    def test_opens_after_threshold_consecutive_failures(self):
        breaker, _ = make()
        fail(breaker, 3)
        assert breaker.state == CircuitState.OPEN
        assert not breaker.allow_request()

    def test_success_resets_the_count(self):
        breaker, _ = make()
        fail(breaker, 2)
        breaker.record_success()
        fail(breaker, 2)
        assert breaker.state == CircuitState.CLOSED

    def test_rate_limit_opens_immediately(self):
        breaker, _ = make()
        fail(breaker, 1, immediate=True)
        assert breaker.state == CircuitState.OPEN


class TestOpenAndHalfOpen:
    def test_skips_until_cooldown_expires(self):
        breaker, clock = make(cooldown=30)
        fail(breaker, 3)
        clock.advance(29.9)
        assert not breaker.allow_request()

    def test_allows_exactly_one_probe_after_cooldown(self):
        breaker, clock = make(cooldown=30)
        fail(breaker, 3)
        clock.advance(30)
        assert breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN
        assert not breaker.allow_request()
        assert not breaker.allow_request()

    def test_probe_success_closes(self):
        breaker, clock = make()
        fail(breaker, 3)
        clock.advance(30)
        assert breaker.allow_request()
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.allow_request()

    def test_probe_failure_reopens_for_a_new_cooldown(self):
        breaker, clock = make(cooldown=30)
        fail(breaker, 3)
        clock.advance(30)
        fail(breaker, 1)
        assert breaker.state == CircuitState.OPEN
        clock.advance(29)
        assert not breaker.allow_request()
        clock.advance(1)
        assert breaker.allow_request()

    def test_released_probe_lets_the_next_request_probe(self):
        breaker, clock = make()
        fail(breaker, 3)
        clock.advance(30)
        assert breaker.allow_request()
        breaker.release()
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.allow_request()

    def test_only_one_concurrent_probe(self):
        breaker, clock = make()
        fail(breaker, 3)
        clock.advance(30)
        allowed = []
        barrier = threading.Barrier(20)

        def attempt():
            barrier.wait()
            allowed.append(breaker.allow_request())

        threads = [threading.Thread(target=attempt) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert allowed.count(True) == 1


def test_reset():
    breaker, _ = make()
    fail(breaker, 3)
    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request()
