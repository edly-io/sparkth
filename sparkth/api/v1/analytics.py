"""Analytics read API — dashboards call these endpoints; they read rollups only.

Never touches the application database or raw events beyond the analytics read
functions. Every endpoint is gated by the ``analytics.read`` permission. (Analytics
is emitted server-side via ``ingest_event`` — validated against the schema on the
``ANALYTICS_EVENTS`` hook; there is no HTTP emission endpoint — this read router is
the analytics HTTP surface.)
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import LoginActivityPoint, get_login_activity
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ

router = APIRouter()


@router.get(
    "/login-activity",
    response_model=list[LoginActivityPoint],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def login_activity(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_analytics_session),
) -> list[LoginActivityPoint]:
    """Return daily login counts (newest first) for the last ``days`` calendar days.

    Days with no logins are omitted from the series (no zero-fill); consumers must
    tolerate gaps.
    """
    return await get_login_activity(session, days)
