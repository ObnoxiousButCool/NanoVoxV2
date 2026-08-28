"""Health probe port.

Each probe answers one question — "is this component reachable?" — and is
responsible for converting its own failure mode into a ``DOWN`` result. A probe
never raises: an unreachable dependency is a health finding, not an error.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.value_objects.health import ComponentHealth


class HealthProbe(ABC):
    """Probes a single named component."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for the probed component, e.g. ``database``."""

    @abstractmethod
    async def check(self) -> ComponentHealth:
        """Probe the component. Must not raise; report failure as ``DOWN``."""
