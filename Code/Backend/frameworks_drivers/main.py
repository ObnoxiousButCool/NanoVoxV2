"""FastAPI application factory and entry point.

Run from ``Code/Backend`` with::

    python -m uvicorn frameworks_drivers.main:app --host 127.0.0.1 --port 8000 --reload

Startup order is deliberate: logging first, so a configuration failure is itself
logged; then the container; then a real connection to the database, so a broken
dependency fails at startup rather than inside the first request.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.use_cases.run_corpus import INTERRUPTED_REASON
from frameworks_drivers.api.errors import register_exception_handlers
from frameworks_drivers.api.v1 import router as api_v1_router
from frameworks_drivers.container import Container, build_container, dispose_container
from frameworks_drivers.middleware.correlation_id import CorrelationIdMiddleware
from frameworks_drivers.middleware.request_logging import RequestLoggingMiddleware
from frameworks_drivers.middleware.unhandled_error import UnhandledErrorMiddleware
from infrastructure.config.settings import Settings, get_settings
from infrastructure.logging.correlation import CORRELATION_ID_HEADER
from infrastructure.logging.setup import configure_logging, shutdown_logging
from infrastructure.persistence.engine import verify_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings)
    logger.info(
        "Starting %s",
        settings.app_name,
        extra={"version": settings.app_version, "environment": settings.app_env},
    )

    container = build_container(settings)
    app.state.container = container
    logger.info(
        "Analysis configuration loaded",
        extra={
            "rubric_version": container.rubric.version,
            "rubric_dimensions": len(container.rubric.dimensions),
            "rubric_gates": len(container.rubric.gates),
            "categories": len(container.taxonomy.categories),
            "l4_categories": len(container.taxonomy.l4_categories),
        },
    )
    try:
        await verify_connection(container.engine)
        await _release_abandoned_runs(container)
        yield
    finally:
        await dispose_container(container)
        logger.info("Shutdown complete")
        shutdown_logging()


async def _release_abandoned_runs(container: Container) -> None:
    """Close out runs whose worker died with the last process.

    The runner is in-process, so a run still marked active at startup belongs to
    a worker that no longer exists. Left alone it would show as live forever and
    block every new run through the single-active-run rule.
    """
    abandoned = await container.run_repository().abandon_active(
        now=container.clock.now(), reason=INTERRUPTED_REASON
    )
    if abandoned:
        logger.warning("Marked %d corpus run(s) as interrupted; they can be resumed.", abandoned)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Tests call this with their own settings."""
    resolved = settings or get_settings()

    app = FastAPI(
        title=f"{resolved.app_name} API",
        version=resolved.app_version,
        summary="Call intelligence for member services.",
        lifespan=lifespan,
        docs_url="/docs" if not resolved.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not resolved.is_production else None,
    )
    app.state.settings = resolved

    # add_middleware prepends, so the last registration is the outermost layer.
    # The resulting order, outermost first, is:
    #
    #   CORS -> CorrelationId -> UnhandledError -> RequestLogging -> routes
    #
    # CORS is outermost so that error responses still carry CORS headers and the
    # browser can read them. CorrelationId sits above the error catch-all so that
    # every response, including a 500, leaves with an ID the client can quote.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origin_list,
        allow_credentials=False,
        # DELETE is here for clearing the corpus. It is not a CORS-safelisted
        # method, so omitting it does not fail at the server: the browser blocks
        # the request after the preflight and the caller sees a network error
        # for a server it never actually reached.
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[CORRELATION_ID_HEADER],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=resolved.api_prefix)
    return app


app = create_app()
