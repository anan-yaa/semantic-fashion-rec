"""Per-request stage timings, reported in the Server-Timing response header.

The search route calls start_timing(); code anywhere below it wraps a stage in
`with timed("name"):`. Durations of repeated stages add up (e.g. hybrid search
running keyword search twice). Outside a request, timed() does nothing.
"""
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_timings: ContextVar[dict[str, float] | None] = ContextVar("stage_timings", default=None)


def start_timing() -> dict[str, float]:
    timings: dict[str, float] = {}
    _timings.set(timings)
    return timings


@contextmanager
def timed(stage: str) -> Iterator[None]:
    timings = _timings.get()
    start = time.perf_counter()
    try:
        yield
    finally:
        if timings is not None:
            timings[stage] = timings.get(stage, 0.0) + (time.perf_counter() - start) * 1000


def server_timing_header(timings: dict[str, float]) -> str:
    """e.g. 'llm;dur=312.4, embed;dur=21.0' (milliseconds, per the Server-Timing spec)."""
    return ", ".join(f"{stage};dur={ms:.1f}" for stage, ms in timings.items())
