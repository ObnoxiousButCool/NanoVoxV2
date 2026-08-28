"""RFC 9457 problem responses.

Every error leaves the API in the same shape, carrying the correlation ID that
ties it to the server-side logs. Stack traces and internal messages are never
returned to the client; unexpected errors are logged in full and answered with a
generic body.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from domain.errors import (
    ConfigurationError,
    DependencyUnavailableError,
    NanoVoxError,
    NotFoundError,
    ValidationError,
)
from infrastructure.logging.correlation import get_correlation_id

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


@dataclass(frozen=True)
class _ErrorPolicy:
    """How one error type is presented to the client.

    ``expose`` is a deliberate, per-error decision rather than a function of the
    status code: "the model provider is unreachable" is a 503 the caller should
    read, while a configuration failure is a 500 whose message could disclose
    connection details.
    """

    status_code: int
    expose: bool


_POLICY_BY_ERROR: dict[type[NanoVoxError], _ErrorPolicy] = {
    ValidationError: _ErrorPolicy(status.HTTP_400_BAD_REQUEST, expose=True),
    NotFoundError: _ErrorPolicy(status.HTTP_404_NOT_FOUND, expose=True),
    DependencyUnavailableError: _ErrorPolicy(status.HTTP_503_SERVICE_UNAVAILABLE, expose=True),
    ConfigurationError: _ErrorPolicy(status.HTTP_500_INTERNAL_SERVER_ERROR, expose=False),
}

# Anything not listed above is by definition unanticipated, so it is never exposed.
_FALLBACK_POLICY = _ErrorPolicy(status.HTTP_500_INTERNAL_SERVER_ERROR, expose=False)

GENERIC_ERROR_MESSAGE = "An unexpected error occurred. Quote the correlation ID when reporting it."

# 422 has no spelling that is both available and undeprecated across the versions
# we support: http.HTTPStatus gained UNPROCESSABLE_CONTENT only in 3.13, while
# Starlette has deprecated its HTTP_422_UNPROCESSABLE_ENTITY alias. The literal is
# stable and unambiguous.
HTTP_422_UNPROCESSABLE_CONTENT = 422


class ProblemDetail(BaseModel):
    """Problem details for an HTTP API, per RFC 9457."""

    type: str = Field(default="about:blank", description="URI identifying the problem type.")
    title: str = Field(description="Short, human-readable summary of the problem type.")
    status: int = Field(description="HTTP status code.")
    detail: str | None = Field(default=None, description="Explanation specific to this occurrence.")
    code: str = Field(description="Stable machine-readable error code.")
    correlation_id: str | None = Field(
        default=None, description="Identifier tying this response to the server logs."
    )


def problem_response(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str | None = None,
) -> JSONResponse:
    """Build a problem+json response carrying the current correlation ID."""
    problem = ProblemDetail(
        title=title,
        status=status_code,
        detail=detail,
        code=code,
        correlation_id=get_correlation_id(),
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _policy_for(error: NanoVoxError) -> _ErrorPolicy:
    for error_type, policy in _POLICY_BY_ERROR.items():
        if isinstance(error, error_type):
            return policy
    return _FALLBACK_POLICY


def register_exception_handlers(app: FastAPI) -> None:
    """Install the handlers that give every error a consistent representation."""

    @app.exception_handler(NanoVoxError)
    async def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
        error = exc if isinstance(exc, NanoVoxError) else NanoVoxError(str(exc))
        policy = _policy_for(error)

        if not policy.expose:
            # The full error goes to the log; the client gets nothing that could
            # disclose internal configuration.
            logger.error("Unhandled domain error", exc_info=error)
            return problem_response(
                status_code=policy.status_code,
                code=error.code,
                title=HTTPStatus(policy.status_code).phrase,
                detail=GENERIC_ERROR_MESSAGE,
            )

        logger.info("Request rejected", extra={"error_code": error.code, "reason": error.message})
        return problem_response(
            status_code=policy.status_code,
            code=error.code,
            title=error.message,
            detail=error.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(_request: Request, exc: Exception) -> JSONResponse:
        detail = None
        if isinstance(exc, RequestValidationError):
            detail = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
        return problem_response(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            code="request_validation_error",
            title="Request validation failed",
            detail=detail,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_request: Request, exc: Exception) -> JSONResponse:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail: str | None = None
        if isinstance(exc, StarletteHTTPException):
            status_code = exc.status_code
            detail = str(exc.detail) if exc.detail else None
        return problem_response(
            status_code=status_code,
            code=f"http_{status_code}",
            title=HTTPStatus(status_code).phrase,
            detail=detail,
        )

    # Note: no handler is registered for bare ``Exception``. Starlette would route
    # it to ServerErrorMiddleware, outside the correlation middleware, producing a
    # response with no correlation ID. UnhandledErrorMiddleware covers that case
    # from inside the middleware stack instead.
