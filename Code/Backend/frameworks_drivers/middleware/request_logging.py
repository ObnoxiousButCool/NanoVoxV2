"""Access logging middleware.

Writes one structured record per request to the dedicated access logger, which
has its own file. Timing uses a monotonic clock so a system clock adjustment
cannot produce a negative duration.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from infrastructure.logging.setup import ACCESS_LOGGER_NAME

logger = logging.getLogger(ACCESS_LOGGER_NAME)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status and duration for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # The exception handlers turn this into a response; the access log
            # still needs a line for the request, so record it and re-raise.
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            raise

        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response
