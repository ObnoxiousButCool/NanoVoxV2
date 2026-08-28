"""The rule that decides what 'healthy' means lives in the domain, and is tested there."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.value_objects.health import ComponentHealth, ComponentStatus, HealthReport

_NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _report(*components: ComponentHealth) -> HealthReport:
    return HealthReport(components=components, checked_at=_NOW)


def test_all_components_up_is_healthy() -> None:
    report = _report(
        ComponentHealth("database", ComponentStatus.UP),
        ComponentHealth("cache", ComponentStatus.UP),
    )

    assert report.status is ComponentStatus.UP
    assert report.is_healthy


def test_one_component_down_makes_the_whole_report_unhealthy() -> None:
    report = _report(
        ComponentHealth("database", ComponentStatus.UP),
        ComponentHealth("cache", ComponentStatus.DOWN, detail="connection refused"),
    )

    assert report.status is ComponentStatus.DOWN
    assert not report.is_healthy


def test_report_with_no_components_is_healthy() -> None:
    assert _report().is_healthy


def test_component_health_is_immutable() -> None:
    component = ComponentHealth("database", ComponentStatus.UP)

    assert component.is_up
    assert component == ComponentHealth("database", ComponentStatus.UP)
