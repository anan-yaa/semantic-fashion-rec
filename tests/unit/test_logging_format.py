"""Structured logging keeps `extra=` fields and the request id."""
import json
import logging

from core.logging import JsonFormatter, RequestIdFilter, TextFormatter, request_id_var


def _record(**extra) -> logging.LogRecord:
    logger = logging.getLogger("t")
    record = logger.makeRecord("t", logging.INFO, __file__, 1, "search_complete", (), None, extra=extra)
    RequestIdFilter().filter(record)
    return record


def test_json_formatter_includes_extras_and_request_id():
    token = request_id_var.set("req-1")
    try:
        out = json.loads(JsonFormatter().format(_record(llm_latency_ms=12.5, llm_used=True)))
    finally:
        request_id_var.reset(token)

    assert out["message"] == "search_complete"
    assert out["request_id"] == "req-1"
    assert out["llm_latency_ms"] == 12.5
    assert out["llm_used"] is True


def test_text_formatter_appends_extras():
    line = TextFormatter("%(message)s").format(_record(search_ms=3))
    assert line == "search_complete search_ms=3"
