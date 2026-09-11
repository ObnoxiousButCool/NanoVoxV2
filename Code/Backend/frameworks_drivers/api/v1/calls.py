"""Calls list and detail endpoints.

The list is sorted by severity rather than by date — the prototype's stated rule,
"the calls that need action surface first". Filters are applied before paging, so
the reported total is the number of matching calls rather than the size of a page.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from application.ports.read_models import CallFilters, CallSort, CallSummary, Page
from domain.aggregation.period import resolve_period
from domain.errors import NotFoundError
from frameworks_drivers.api.dependencies import AnalysisRepositoryDep, ReadModelsDep
from frameworks_drivers.api.v1.analyses import AnalysisResponse, to_response

router = APIRouter(tags=["calls"])

DEFAULT_LIMIT = 25
MAX_LIMIT = 200


class CallSummaryResponse(BaseModel):
    id: int
    reference: str
    title: str
    summary: str
    category: str
    agent_name: str | None
    member_id: str | None = None
    member_name: str | None = None
    caller_type: str | None = None
    resolution: str
    score: int
    score_status: str
    tier: str
    source: str
    analysed_at: datetime
    signal_codes: list[str]
    broker_names: list[str]


class CallsPageResponse(BaseModel):
    items: list[CallSummaryResponse]
    total: int = Field(description="Matching calls, before paging.")
    limit: int
    offset: int
    has_more: bool


def _summary(row: CallSummary) -> CallSummaryResponse:
    return CallSummaryResponse(
        id=row.id,
        reference=row.reference,
        title=row.title,
        summary=row.summary,
        category=row.category_code,
        agent_name=row.agent_name,
        member_id=row.member_id,
        member_name=row.member_name,
        caller_type=row.caller_type,
        resolution=row.resolution,
        score=row.score,
        score_status=row.score_status,
        tier=row.tier,
        source=row.source,
        analysed_at=row.analysed_at,
        signal_codes=list(row.signal_codes),
        broker_names=list(row.broker_names),
    )


def _page(page: Page) -> CallsPageResponse:
    return CallsPageResponse(
        items=[_summary(row) for row in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        has_more=page.has_more,
    )


@router.get("/calls", response_model=CallsPageResponse, summary="List analyzed calls")
async def list_calls(
    repository: ReadModelsDep,
    category: Annotated[str | None, Query(description="Call category code.")] = None,
    agent: Annotated[str | None, Query(description="Agent name.")] = None,
    resolution: Annotated[str | None, Query(description="Outcome, e.g. UNRESOLVED.")] = None,
    max_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    has_broker_signal: Annotated[bool | None, Query()] = None,
    broker: Annotated[str | None, Query(description="Broker name attributed on the call.")] = None,
    caller: Annotated[
        str | None, Query(description="Who called: MEMBER, EMPLOYER or BROKER.")
    ] = None,
    member: Annotated[
        str | None, Query(description="Member identifier, as stated in the call.")
    ] = None,
    signal: Annotated[str | None, Query(description="Signal code, e.g. clinical_risk.")] = None,
    hour: Annotated[
        int | None,
        Query(
            ge=0,
            le=23,
            description=(
                "The hour of the day a call started, 0-23, in the wall-clock "
                "the source stated. Matches the hourly chart's bars."
            ),
        ),
    ] = None,
    l4_category: Annotated[
        str | None,
        Query(
            description=(
                "L4 finding category code. The finding taxonomy, not the call "
                "category: a Coverage & Benefits call can raise a Process "
                "Breakdown finding."
            )
        ),
    ] = None,
    month: Annotated[
        date | None,
        Query(
            description=(
                "Narrow to calls started in this date's calendar month. The same "
                "range the dashboard's cards use for the same month, so a figure "
                "there and this list agree."
            )
        ),
    ] = None,
    search: Annotated[str | None, Query(description="Matches title, summary or reference.")] = None,
    sort: Annotated[
        CallSort,
        Query(description="Column to order by. 'severity' is what needs action first."),
    ] = CallSort.SEVERITY,
    direction: Annotated[Literal["asc", "desc"], Query()] = "asc",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CallsPageResponse:
    filters = CallFilters(
        category_code=category,
        agent_name=agent,
        resolution=resolution,
        max_score=max_score,
        min_score=min_score,
        has_broker_signal=has_broker_signal,
        broker_name=broker,
        caller_type=caller,
        member_id=member,
        signal_code=signal,
        l4_category_code=l4_category,
        started_hour=hour,
        search=search,
        period=resolve_period(None, month),
    )
    return _page(
        await repository.list_calls(
            filters,
            limit=limit,
            offset=offset,
            sort=sort,
            descending=direction == "desc",
        )
    )


@router.get("/calls/{call_id}", response_model=AnalysisResponse, summary="One call in full")
async def get_call(call_id: int, repository: AnalysisRepositoryDep) -> AnalysisResponse:
    analysis = await repository.get(call_id)
    if analysis is None:
        raise NotFoundError(f"Call {call_id} does not exist.")
    return to_response(analysis, call_id)
