"""Provider listing endpoint.

Feeds the provider/model picker on the Analyze screen. Every provider is listed,
including ones that are unusable right now, with the reason — an empty list would
tell the user nothing about why they cannot proceed.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from application.use_cases.list_providers import ProviderDescription
from frameworks_drivers.api.dependencies import ListProvidersDep

router = APIRouter(tags=["providers"])


class ProviderResponse(BaseModel):
    name: str
    model: str
    configured: bool = Field(description="Whether the provider's required settings are present.")
    reachable: bool = Field(description="Whether it answered a probe just now.")
    implemented: bool = Field(description="False for providers registered but not built.")
    selectable: bool = Field(description="Whether an analysis may be run against it.")
    is_default: bool
    billable: bool = Field(
        description="Whether running against this provider is charged for per token."
    )
    detail: str | None = None


class ProvidersResponse(BaseModel):
    default: str
    providers: list[ProviderResponse]


def _to_response(description: ProviderDescription) -> ProviderResponse:
    return ProviderResponse(
        name=description.name,
        model=description.model,
        configured=description.configured,
        reachable=description.reachable,
        implemented=description.implemented,
        selectable=description.selectable,
        is_default=description.is_default,
        billable=description.billable,
        detail=description.detail,
    )


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    summary="List model providers and their current availability",
)
async def list_providers(use_case: ListProvidersDep) -> ProvidersResponse:
    descriptions = await use_case.execute()
    return ProvidersResponse(
        default=use_case.default_name,
        providers=[_to_response(description) for description in descriptions],
    )
