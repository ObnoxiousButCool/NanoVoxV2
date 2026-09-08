"""Taxonomy endpoint.

The frontend renders filters and labels from this rather than hard-coding a
vocabulary, so adding a category to ``taxonomy.yaml`` reaches the UI without a
frontend change — the other half of DEC-02.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from domain.value_objects.caller_type import CallerType
from domain.value_objects.resolution import Resolution
from domain.value_objects.severity import Severity
from frameworks_drivers.api.dependencies import ContainerDep

router = APIRouter(tags=["system"])


class CategoryEntry(BaseModel):
    code: str
    label: str
    description: str | None


class L4CategoryEntry(BaseModel):
    code: str
    label: str
    owner: str
    default_severity: str


class SignalTypeEntry(BaseModel):
    code: str
    label: str
    severity: str


class TierThresholdsEntry(BaseModel):
    good: int
    average: int
    min_calls_for_tier_rating: int


class TaxonomyResponse(BaseModel):
    categories: list[CategoryEntry]
    l4_categories: list[L4CategoryEntry]
    signal_types: list[SignalTypeEntry]
    sentiment_states: list[str]
    resolutions: list[str]
    caller_types: list[str]
    severities: list[str]
    tiers: TierThresholdsEntry
    rubric_version: str


@router.get("/taxonomy", response_model=TaxonomyResponse, summary="Controlled vocabularies")
async def get_taxonomy(container: ContainerDep) -> TaxonomyResponse:
    taxonomy = container.taxonomy
    rubric = container.rubric
    return TaxonomyResponse(
        categories=[
            CategoryEntry(code=item.code, label=item.label, description=item.description)
            for item in taxonomy.categories
        ],
        l4_categories=[
            L4CategoryEntry(
                code=item.code,
                label=item.label,
                owner=item.owner.name,
                default_severity=item.default_severity.value,
            )
            for item in taxonomy.l4_categories
        ],
        signal_types=[
            SignalTypeEntry(code=item.code, label=item.label, severity=item.severity.value)
            for item in taxonomy.signal_types
        ],
        sentiment_states=list(taxonomy.sentiment_states),
        resolutions=[member.value for member in Resolution],
        # The vocabulary, not the values present in the data: an empty option is
        # information — nobody from that population called — and a dropdown
        # built from a GROUP BY would silently drop it.
        caller_types=[member.value for member in CallerType],
        severities=[member.value for member in Severity],
        tiers=TierThresholdsEntry(
            good=rubric.tiers.good,
            average=rubric.tiers.average,
            min_calls_for_tier_rating=rubric.min_calls_for_tier_rating,
        ),
        rubric_version=rubric.version,
    )
