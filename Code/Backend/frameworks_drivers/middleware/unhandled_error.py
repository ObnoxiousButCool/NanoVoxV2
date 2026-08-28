"""Catch-all for unanticipated exceptions.

This is deliberately middleware rather than an ``@app.exception_handler(Exception)``.
Starlette routes a handler registered for ``Exception`` to ``ServerErrorMiddleware``,
which sits outside every user middleware — so its response never passes back
through the correlation middleware and would reach the client with no
``X-Correlation-ID`` header. Catching here, inside the correlation scope, means
every error response the client sees can be traced to a log entry.

``ServerErrorMiddleware`` still stands behind this as the final backstop for a
failure in the middleware stack itself.
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from frameworks_drivers.api.errors import GENERIC_ERROR_MESSAGE, problem_response

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware(BaseHTTPMiddleware):
    """Turns any escaped exception into a correlated problem response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            # The full traceback goes to the log; the client gets the correlation
            # ID and nothing else.
            logger.exception(
                "Unhandled exception",
                exc_info=exc,
                extra={"method": request.method, "path": request.url.path},
            )
            return problem_response(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                code="internal_error",
                title=HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                detail=GENERIC_ERROR_MESSAGE,
            )
