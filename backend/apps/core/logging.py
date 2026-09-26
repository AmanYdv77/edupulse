"""
Structured, PII-free JSON logging utilities and Request ID context tracking for EduPulse.
"""

import contextvars
import json
import logging
from datetime import UTC, datetime
from typing import Any

# Global contextvar holding the unique correlation ID for the current request/task execution
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Retrieve the current request correlation ID, or empty string if not within a request context."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the current request correlation ID."""
    _request_id_ctx.set(request_id)


class RequestIDFilter(logging.Filter):
    """
    Logging filter that injects the active request_id from contextvars into every LogRecord.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JSONLogFormatter(logging.Formatter):
    """
    Standard-library-only JSON log formatter.
    Emits single-line UTC ISO-8601 formatted JSON containing timestamp, level, logger, message, and request_id.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Generate clean UTC ISO-8601 timestamp with 'Z' suffix
        timestamp = (
            datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z")
        )

        message = record.getMessage()

        log_entry: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "request_id": getattr(record, "request_id", "-"),
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)
