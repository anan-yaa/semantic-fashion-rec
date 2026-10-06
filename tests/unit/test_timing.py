"""Unit tests for per-request stage timing."""
import time

from app.services.timing import server_timing_header, start_timing, timed


def test_records_stage_durations():
    timings = start_timing()
    with timed("llm"):
        time.sleep(0.01)
    assert timings["llm"] >= 10


def test_repeated_stages_add_up():
    timings = start_timing()
    with timed("keyword_db"):
        time.sleep(0.005)
    with timed("keyword_db"):
        time.sleep(0.005)
    assert timings["keyword_db"] >= 10


def test_records_even_when_the_stage_raises():
    timings = start_timing()
    try:
        with timed("embed"):
            raise ValueError
    except ValueError:
        pass
    assert "embed" in timings


def test_header_format():
    assert server_timing_header({"llm": 312.44, "embed": 21.0}) == "llm;dur=312.4, embed;dur=21.0"
