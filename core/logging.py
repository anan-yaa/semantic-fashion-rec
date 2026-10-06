import json
import logging
import sys
from contextvars import ContextVar

from core.config import settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Attributes every LogRecord has; anything else came from `extra=` and is worth emitting.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def _extras(record: logging.LogRecord) -> dict:
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "request_id": record.request_id,
            "message": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        return f"{line} {extras}" if extras else line


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if settings.log_format.lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = TextFormatter("%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.error").setLevel(log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
