"""Structured JSON logging with request-ID correlation.

The ``request_id`` ContextVar is populated per-request by
``ai_tutor.middleware.RequestIdMiddleware``. ``RequestIdFilter`` copies
that value onto every emitted ``LogRecord`` so the JSON formatter can
include it without each call site having to thread it manually.

This module deliberately uses only the standard library: the brief allowed
either ``python-json-logger`` or a small custom formatter. Avoiding the
extra dependency keeps the install path narrow for the OSS-POC framing.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextvars import ContextVar
from typing import Optional

REQUEST_ID_HEADER = "X-Request-Id"
_REQUEST_ID_DEFAULT = "-"

# Module-level ContextVar shared with middleware. Default value is "-" so
# log lines emitted outside a request (startup / shutdown / background)
# still carry a valid string field.
request_id_var: ContextVar[str] = ContextVar("request_id", default=_REQUEST_ID_DEFAULT)


def get_request_id() -> str:
    """Return the request id bound to the current async context."""
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Inject the current ``request_id`` ContextVar value onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


# Standard ``LogRecord`` attributes we should not surface as caller "extras".
_RESERVED_LOGRECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


class JsonFormatter(logging.Formatter):
    """Minimal stdlib-only JSON log formatter.

    Emits one line per record with ``timestamp``, ``level``, ``logger``,
    ``request_id``, ``message`` and any caller-supplied extras attached via
    ``logger.*(..., extra={...})``. Falls back to ``repr`` for values that
    are not directly JSON-serializable so a misshapen extra cannot break
    the log pipeline.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", _REQUEST_ID_DEFAULT),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if (
                key in _RESERVED_LOGRECORD_ATTRS
                or key in payload
                or key.startswith("_")
            ):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_LOGGING_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    """Apply JSON-formatted, request-ID-aware logging to root + uvicorn loggers.

    Idempotent: calling twice has no extra effect. Uvicorn loggers have
    ``propagate`` set to False so their records are not emitted twice
    when both they and the root logger have handlers attached.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    # ``or "INFO"`` keeps the result narrowed to ``str`` for mypy even when
    # ``level`` is None and the env lookup somehow yields a falsy value.
    target_level = (level or os.getenv("CALCANIM_LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(target_level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.setLevel(target_level)
        lg.propagate = False

    _LOGGING_CONFIGURED = True
