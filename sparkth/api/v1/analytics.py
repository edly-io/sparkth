"""Analytics read API — the dashboards and Explore call these endpoints.

The dashboards read rollups, ``/events`` lists the registered event types and ``/query`` counts
raw events, naming actors from the application database. Every endpoint is gated by the
``analytics.read`` permission, and ``/query`` also by ``user.read``. (Analytics is emitted
server-side via ``ingest_event`` — validated against the schema on the ``ANALYTICS_EVENTS``
hook; there is no HTTP emission endpoint — this read router is the analytics HTTP surface.)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession as AppSession

from sparkth.lib.analytics import (
    EventCatalogEntry,
    ExploreQuery,
    ExploreQueryError,
    ExploreResult,
    LoginsPoint,
    RangeQuery,
    SummaryCount,
    event_catalog,
    get_logins,
    measure_raw_events,
    summarize,
)
from sparkth.lib.db import get_analytics_session, get_async_session
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.permissions import ANALYTICS_READ, USER_READ
from sparkth.services.users import get_usernames

register_exception_handler(ExploreQueryError, status.HTTP_422_UNPROCESSABLE_CONTENT)

router = APIRouter()


@router.get(
    "/logins",
    response_model=list[LoginsPoint],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def logins(
    query: Annotated[RangeQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[LoginsPoint]:
    """Return login counts per bucket and sign-in method, oldest first.

    Sparse: buckets or methods with no logins are omitted; consumers zero-fill.
    The range filters on the UTC day, so for week/month buckets the first bucket's
    label is its start date and can fall before `from`; clients zero-filling should
    floor `from` to the bucket start.
    """
    return await get_logins(session, query.from_, query.to, query.bucket)


@router.get(
    "/summary",
    response_model=list[SummaryCount],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def summary(
    query: Annotated[RangeQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[SummaryCount]:
    """Return every headline figure for the range and for the equal-length range before it.

    Labels are in the request language, so never cache the response across users. `bucket` is
    ignored.
    """
    return await summarize(session, query.from_, query.to)


@router.get(
    "/events",
    response_model=list[EventCatalogEntry],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def events() -> list[EventCatalogEntry]:
    """Return every registered event type with its payload fields, sorted by type."""
    return event_catalog()


@router.get(
    "/query",
    response_model=ExploreResult,
    dependencies=[
        Depends(ANALYTICS_READ.require_in_global_scope()),
        Depends(USER_READ.require_in_global_scope()),
    ],
)
async def query_events(
    query: Annotated[ExploreQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
    app_session: AppSession = Depends(get_async_session),
) -> ExploreResult:
    """Measure one event type's raw events per bucket, filtered and grouped by payload fields.

    Sparse. Grouped results keep the top 20 groups by range total and set `truncated` when more
    existed. An unknown event type or field, or a value that does not fit its field, is a 422.
    Grouped by actor, `actor_names` maps user ids to usernames. Needs `analytics.read` and `user.read`.
    """
    result = await measure_raw_events(session, query)
    if query.group_by == "actor":
        ids = {int(t.group) for t in result.totals if t.group is not None and t.group.isdecimal()}
        result.actor_names = {str(uid): name for uid, name in (await get_usernames(app_session, ids)).items()}
    return result
