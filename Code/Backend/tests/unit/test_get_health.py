"""The health use case aggregates probes without letting one of them take the rest down."""

from __future__ import annotations

from datetime import datetime, timezone

from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from application.use_cases.get_health import GetHealth
from domain.value_objects.health import ComponentHealth, ComponentStatus

_NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


class StubProbe(HealthProbe):
    def __init__(self, name: str, status: ComponentStatus) -> None:
        self._name = name
        self._status = status

    @property
    def name(self) -> str:
        return self._name

    async def check(self) -> ComponentHealth:
        return ComponentHealth(name=self._name, status=self._status)


class ExplodingProbe(HealthProbe):
    """A probe that breaks its contract by raising."""

    @property
    def name(self) -> str:
        return "broken"

    async def check(self) -> ComponentHealth:
        raise RuntimeError("probe is broken")


async def test_reports_every_probe_and_stamps_the_time() -> None:
    use_case = GetHealth(
        probes=[
            StubProbe("database", ComponentStatus.UP),
            StubProbe("provider", ComponentStatus.UP),
        ],
        clock=FixedClock(),
    )

    report = await use_case.execute()

    assert report.checked_at == _NOW
    assert [component.name for component in report.components] == ["database", "provider"]
    assert report.is_healthy


async def test_a_down_component_makes_the_report_unhealthy() -> None:
    use_case = GetHealth(
        probes=[
            StubProbe("database", ComponentStatus.DOWN),
            StubProbe("provider", ComponentStatus.UP),
        ],
        clock=FixedClock(),
    )

    report = await use_case.execute()

    assert not report.is_healthy


async def test_a_raising_probe_is_reported_down_without_hiding_the_others() -> None:
    use_case = GetHealth(
        probes=[ExplodingProbe(), StubProbe("database", ComponentStatus.UP)],
        clock=FixedClock(),
    )

    report = await use_case.execute()

    broken, database = report.components
    assert broken.name == "broken"
    assert broken.status is ComponentStatus.DOWN
    assert broken.detail == "probe raised RuntimeError"
    assert database.status is ComponentStatus.UP
