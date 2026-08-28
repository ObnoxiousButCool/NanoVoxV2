"""Logging configuration.

Controlled entirely by configuration (D5): when ``LOG_ENABLED`` is false no
handlers are attached and no files are created, so switching logging off leaves
no trace on disk rather than merely raising the threshold.

Files rotate at midnight and ``LOG_RETENTION_DAYS`` rotated files are kept.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domain.errors import ConfigurationError
from infrastructure.config.settings import Settings
from infrastructure.logging.correlation import CorrelationIdFilter
from infrastructure.logging.llm_audit import LLM_AUDIT_LOGGER_NAME

APP_LOG_FILENAME = "nanovox-app.log"
ACCESS_LOG_FILENAME = "nanovox-access.log"
LLM_AUDIT_LOG_FILENAME = "nanovox-llm-audit.log"

ACCESS_LOGGER_NAME = "nanovox.access"

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(correlation_id)s] %(name)s: %(message)s"

# Attributes present on every LogRecord. Anything else was supplied by the caller
# through ``extra=`` and belongs in the structured payload.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
        "correlation_id",
        # Uvicorn attaches an ANSI-coloured copy of its own message; it is
        # unreadable in a file and duplicates "message".
        "color_message",
    }
)


class JsonFormatter(logging.Formatter):
    """Renders a record as a single JSON object, one per line.

    Hand-rolled rather than pulled from a dependency: the output shape is small,
    fixed, and something we want to control precisely for log analysis.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, "correlation_id", "-"),
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def _build_formatter(settings: Settings) -> logging.Formatter:
    if settings.log_format == "json":
        return JsonFormatter()
    return logging.Formatter(_TEXT_FORMAT)


def _ensure_log_dir(log_dir: Path) -> None:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(
            f"LOG_DIR is not writable: {log_dir}",
            detail=str(exc),
        ) from exc


def _file_handler(
    log_dir: Path,
    filename: str,
    settings: Settings,
    formatter: logging.Formatter,
) -> logging.Handler:
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / filename,
        when="midnight",
        backupCount=settings.log_retention_days,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())
    return handler


def _reset(*loggers: logging.Logger) -> None:
    for logger in loggers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()


def configure_logging(settings: Settings) -> None:
    """Install logging handlers according to configuration.

    Safe to call more than once: existing handlers are removed first, so a reload
    does not duplicate every log line.
    """
    root = logging.getLogger()
    access = logging.getLogger(ACCESS_LOGGER_NAME)
    audit = logging.getLogger(LLM_AUDIT_LOGGER_NAME)
    _reset(root, access, audit)

    # Access and audit records go to their own files; propagating them would
    # duplicate every request and every model call into the app log.
    access.propagate = False
    audit.propagate = False

    if not settings.log_enabled:
        root.addHandler(logging.NullHandler())
        access.addHandler(logging.NullHandler())
        audit.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 1)
        access.setLevel(logging.CRITICAL + 1)
        audit.setLevel(logging.CRITICAL + 1)
        return

    _ensure_log_dir(settings.log_dir)
    formatter = _build_formatter(settings)
    level = getattr(logging, settings.log_level)

    root.setLevel(level)
    root.addHandler(_file_handler(settings.log_dir, APP_LOG_FILENAME, settings, formatter))

    access.setLevel(level)
    access.addHandler(_file_handler(settings.log_dir, ACCESS_LOG_FILENAME, settings, formatter))

    # The audit log is always at INFO: it is a cost and provenance record, and
    # raising the global level to WARNING must not silently stop collecting it.
    audit.setLevel(logging.INFO)
    audit.addHandler(_file_handler(settings.log_dir, LLM_AUDIT_LOG_FILENAME, settings, formatter))

    if settings.log_to_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.addFilter(CorrelationIdFilter())
        root.addHandler(console)

    # Uvicorn installs its own handlers; route its records through ours so every
    # line in the file shares one format.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        _reset(uvicorn_logger)
        uvicorn_logger.propagate = True

    # Uvicorn's access log is silenced entirely: RequestLoggingMiddleware already
    # records every request, with a correlation ID and a duration, in the access
    # file. Leaving both on would log each request twice, once without an ID.
    uvicorn_access = logging.getLogger("uvicorn.access")
    _reset(uvicorn_access)
    uvicorn_access.propagate = False
    uvicorn_access.addHandler(logging.NullHandler())


def shutdown_logging() -> None:
    """Detach and close handlers. Used on application shutdown and between tests."""
    _reset(
        logging.getLogger(),
        logging.getLogger(ACCESS_LOGGER_NAME),
        logging.getLogger(LLM_AUDIT_LOGGER_NAME),
    )
