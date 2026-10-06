"""Unit tests for the load-test helpers."""
import pytest

from app.services.eval.system_health import (
    RequestResult,
    median_of_runs,
    parse_server_timing,
    percentiles,
    summarize,
)


def test_parse_server_timing():
    assert parse_server_timing("llm;dur=312.4, embed;dur=21, total;desc=x;dur=400") == {
        "llm": 312.4, "embed": 21.0, "total": 400.0,
    }


@pytest.mark.parametrize("header", [None, "", "garbage", "llm;dur=abc"])
def test_parse_server_timing_ignores_missing_or_malformed(header):
    assert parse_server_timing(header) == {}


def test_percentiles():
    values = list(range(1, 101))
    p = percentiles(values)
    assert p["p50"] == pytest.approx(50.5)
    assert p["p95"] == pytest.approx(95.05)
    assert p["max"] == 100


def test_summarize_counts_errors_and_excludes_them_from_latency():
    results = [
        RequestResult(status=200, latency_ms=100, stages={"llm": 40}, used_llm=True),
        RequestResult(status=200, latency_ms=300, stages={"llm": 60}, used_llm=False, fallback_reason="unsupported_query"),
        RequestResult(status=500, latency_ms=5),
        RequestResult(status=None, latency_ms=8000, error="ReadTimeout"),
    ]

    s = summarize(results, wall_seconds=2.0)

    assert s["requests"] == 4
    assert s["succeeded"] == 2
    assert s["error_rate"] == 0.5
    assert s["errors"] == {"HTTP 500": 1, "ReadTimeout": 1}
    assert s["throughput_rps"] == 1.0
    assert s["latency_ms"]["max"] == 300
    assert s["stages_ms"]["llm"]["p50"] == pytest.approx(50)
    assert s["llm_used_rate"] == 0.5
    assert s["llm_fallbacks"] == {"unsupported_query": 1}


def test_median_of_runs():
    runs = [{"latency_ms": {"p95": 10}}, {"latency_ms": {"p95": 30}}, {"latency_ms": {"p95": 20}}]
    assert median_of_runs(runs, [["latency_ms", "p95"], ["missing"]]) == {"latency_ms.p95": 20, "missing": None}
