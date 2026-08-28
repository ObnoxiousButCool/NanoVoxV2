"""Health reporting value objects.

Kept in the domain because "the system is healthy only when every checked
component is up" is a rule, not a transport concern. The delivery layer decides
the status code; it does not decide what healthy means.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ComponentStatus(str, Enum):
    """Outcome of probing a single component."""

    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class ComponentHealth:
    """The result of probing one named component."""

    name: str
    status: ComponentStatus
    detail: str | None = None

    @property
    def is_up(self) -> bool:
        return self.status is ComponentStatus.UP


@dataclass(frozen=True)
class HealthReport:
    """Aggregate health across every probed component."""

    components: tuple[ComponentHealth, ...]
    checked_at: datetime

    @property
    def status(self) -> ComponentStatus:
        """Healthy only if every component is up.

        An empty component set is reported as up: nothing was claimed, so nothing
        is broken.
        """
        if all(component.is_up for component in self.components):
            return ComponentStatus.UP
        return ComponentStatus.DOWN

    @property
    def is_healthy(self) -> bool:
        return self.status is ComponentStatus.UP
