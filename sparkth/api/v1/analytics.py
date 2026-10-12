"""Analytics read API — dashboards call these endpoints; they read rollups only.

Never touches the application database or raw events beyond the analytics read
functions. Every endpoint is gated by the ``analytics.read`` permission. (Analytics
is emitted server-side via ``ingest_event`` — validated against the schema on the
``ANALYTICS_EVENTS`` hook; there is no HTTP emission endpoint — this read router is
the analytics HTTP surface.)
"""

from datetime import date
from typing import Annotated, Self

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import Bucket, LoginActivityPoint, LoginsPoint, get_login_activity, get_logins
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ

router = APIRouter()

# Inclusive day count; a leap year fits.
MAX_RANGE_DAYS = 366


class LoginsQuery(BaseModel):
    """Query for ``GET /logins``: an inclusive UTC day range and a bucket width."""

    from_: date = Field(alias="from")
    to: date
    bucket: Bucket = Bucket.day

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.from_ > self.to:
            raise ValueError("'from' must not be after 'to'")
        if (self.to - self.from_).days + 1 > MAX_RANGE_DAYS:
            raise ValueError(f"range must not exceed {MAX_RANGE_DAYS} days")
        return self


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


@router.get(
    "/logins",
    response_model=list[LoginsPoint],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def logins(
    query: Annotated[LoginsQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[LoginsPoint]:
    """Return login counts per bucket and sign-in method, oldest first.

    Sparse: buckets or methods with no logins are omitted; consumers zero-fill.
    The range filters on the UTC day, so for week/month buckets the first bucket's
    label is its start date and can fall before `from`; clients zero-filling should
    floor `from` to the bucket start.
    """
    return await get_logins(session, query.from_, query.to, query.bucket)
