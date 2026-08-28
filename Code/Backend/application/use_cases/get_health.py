"""Report the health of every registered component."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from domain.value_objects.health import ComponentHealth, ComponentStatus, HealthReport


class GetHealth:
    """Probes every registered component concurrently and aggregates the result."""

    def __init__(self, probes: Sequence[HealthProbe], clock: Clock) -> None:
        self._probes = tuple(probes)
        self._clock = clock

    async def execute(self) -> HealthReport:
        results = await asyncio.gather(
            *(probe.check() for probe in self._probes),
            return_exceptions=True,
        )

        components: list[ComponentHealth] = []
        for probe, result in zip(self._probes, results, strict=True):
            if isinstance(result, ComponentHealth):
                components.append(result)
            else:
                # A probe is contractually forbidden from raising. If one does, the
                # component is reported down rather than failing the whole endpoint —
                # a broken probe must not hide the health of everything else.
                components.append(
                    ComponentHealth(
                        name=probe.name,
                        status=ComponentStatus.DOWN,
                        detail=f"probe raised {type(result).__name__}",
                    )
                )

        return HealthReport(components=tuple(components), checked_at=self._clock.now())
