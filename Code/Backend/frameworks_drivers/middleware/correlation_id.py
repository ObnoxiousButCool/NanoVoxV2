"""Correlation ID middleware.

Honours an inbound ``X-Correlation-ID`` so a caller can trace a request across
services, and generates one otherwise. The value is bound to the context for the
lifetime of the request and echoed back on the response.

Must be the outermost middleware: anything registered outside it would log
without a correlation ID.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from infrastructure.logging.correlation import (
    CORRELATION_ID_HEADER,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)

# An inbound value is echoed rather than trusted for anything, so it is only
# length-capped to keep a hostile header out of the log files.
_MAX_INBOUND_LENGTH = 64


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Binds a correlation ID to every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get(CORRELATION_ID_HEADER, "").strip()
        correlation_id = inbound[:_MAX_INBOUND_LENGTH] if inbound else new_correlation_id()

        token = set_correlation_id(correlation_id)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
