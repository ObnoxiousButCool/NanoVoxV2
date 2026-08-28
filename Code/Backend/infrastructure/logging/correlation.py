"""Correlation identifiers.

Every request is tagged with a correlation ID that is attached to each log record
it produces and returned to the caller in both the response header and any error
body. One identifier therefore ties a browser error to the exact server-side
work that produced it.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar, Token

CORRELATION_ID_HEADER = "X-Correlation-ID"
_UNSET = "-"

_correlation_id: ContextVar[str | None] = ContextVar("nanovox_correlation_id", default=None)


def new_correlation_id() -> str:
    """Generate a fresh correlation identifier."""
    return uuid.uuid4().hex


def set_correlation_id(value: str) -> Token[str | None]:
    """Bind a correlation ID to the current context, returning a reset token."""
    return _correlation_id.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation ID that was bound before ``token`` was issued."""
    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    """Return the correlation ID bound to the current context, if any."""
    return _correlation_id.get()


class CorrelationIdFilter(logging.Filter):
    """Attaches the current correlation ID to every record.

    Implemented as a filter rather than as formatter logic so that both the JSON
    and text formatters see the attribute, and so records emitted outside a
    request still carry a defined value.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or _UNSET
        return True
