"""Database health probe."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from application.ports.health_probe import HealthProbe
from domain.value_objects.health import ComponentHealth, ComponentStatus

logger = logging.getLogger(__name__)

COMPONENT_NAME = "database"


class DatabaseHealthProbe(HealthProbe):
    """Confirms the database is reachable by issuing a trivial query."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return COMPONENT_NAME

    async def check(self) -> ComponentHealth:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            # An unreachable database is a health finding, not a request failure:
            # the endpoint must still report on every other component.
            logger.warning("Database health probe failed", exc_info=exc)
            return ComponentHealth(
                name=self.name,
                status=ComponentStatus.DOWN,
                detail=type(exc).__name__,
            )
        return ComponentHealth(name=self.name, status=ComponentStatus.UP)
