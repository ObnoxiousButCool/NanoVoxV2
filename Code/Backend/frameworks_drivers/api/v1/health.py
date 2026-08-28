"""Health endpoint.

Reports per-component health rather than a bare "ok", so a failure names the
component that caused it. Answers 503 when any component is down, which is what
a container orchestrator or the frontend's diagnostics view needs in order to act.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from domain.value_objects.health import ComponentStatus, HealthReport
from frameworks_drivers.api.dependencies import GetHealthDep, SettingsDep

router = APIRouter(tags=["system"])


class ComponentHealthResponse(BaseModel):
    name: str
    status: ComponentStatus
    detail: str | None = None


class HealthResponse(BaseModel):
    status: ComponentStatus
    application: str
    version: str
    environment: str
    checked_at: datetime
    components: list[ComponentHealthResponse] = Field(default_factory=list)


def _to_response(report: HealthReport, name: str, version: str, environment: str) -> HealthResponse:
    return HealthResponse(
        status=report.status,
        application=name,
        version=version,
        environment=environment,
        checked_at=report.checked_at,
        components=[
            ComponentHealthResponse(name=c.name, status=c.status, detail=c.detail)
            for c in report.components
        ],
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Report application and dependency health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "A component is unavailable."}},
)
async def get_health(
    response: Response,
    use_case: GetHealthDep,
    settings: SettingsDep,
) -> HealthResponse:
    report = await use_case.execute()
    if not report.is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return _to_response(
        report,
        name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
