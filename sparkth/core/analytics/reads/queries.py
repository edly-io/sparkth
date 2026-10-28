"""Core's own analytics reads: logins per bucket, and the Overview figures.

The core figures (logins, active users, signups) are seeded on the ``SUMMARY_FIGURES`` hook at
import, and ``summarize`` counts every registered figure for a range and for the equal-length range
before it.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.core.analytics.hooks import SUMMARY_FIGURES
from sparkth.core.analytics.models import raw_events
from sparkth.core.analytics.reads.buckets import in_days
from sparkth.core.analytics.reads.enums import Bucket
from sparkth.core.analytics.reads.rollups import read_rollup
from sparkth.core.analytics.reads.schemas import LoginsPoint, SummaryCount
from sparkth.core.analytics.types import SummaryFigure
from sparkth.core.i18n import gettext, gettext_noop


async def get_logins(session: AsyncSession, from_: date, to: date, bucket: Bucket) -> list[LoginsPoint]:
    """Return login counts per ``bucket`` and sign-in method for days ``from_``..``to`` (inclusive).

    Oldest bucket first, methods ordered bytewise (``unknown`` first) within a bucket. Sparse:
    buckets or methods with no logins are omitted, so callers zero-fill. A login whose payload has
    no ``method`` counts as ``unknown``.
    """
    rows = await read_rollup(
        session,
        aggregate="login_activity_daily_by_method",
        event_types=("user.logged_in",),
        dims={"method": "method"},
        count_column="login_count",
        from_=from_,
        to=to,
        bucket=bucket,
    )
    return [LoginsPoint.model_validate({**r, "method": r["method"] or "unknown"}) for r in rows]


async def _logins(session: AsyncSession, from_: date, to: date) -> int:
    return sum(p.login_count for p in await get_logins(session, from_, to, Bucket.month))


async def _active_users(session: AsyncSession, from_: date, to: date) -> int:
    # ponytail: scans raw_events over the range; add an (occurred_at, actor_id) index or a daily
    # distinct-actor rollup if it gets slow. Aggregates can't count distinct across days.
    query = select(func.count(raw_events.c.actor_id.distinct())).where(*in_days(from_, to))
    return int(await session.scalar(query) or 0)


async def _signups(session: AsyncSession, from_: date, to: date) -> int:
    query = select(func.count()).where(raw_events.c.event_type == "user.registered", *in_days(from_, to))
    return int(await session.scalar(query) or 0)


SUMMARY_FIGURES.add_item(SummaryFigure("logins", gettext_noop("Logins"), _logins, view="logins", order=10))
SUMMARY_FIGURES.add_item(SummaryFigure("active_users", gettext_noop("Active users"), _active_users, order=20))
SUMMARY_FIGURES.add_item(SummaryFigure("signups", gettext_noop("Signups"), _signups, order=30))


async def summarize(session: AsyncSession, from_: date, to: date) -> list[SummaryCount]:
    """Count every registered figure for ``from_``..``to`` and for the same number of days before.

    Labels are translated into the request locale. Ordered by ``order``, then ``key``.
    """
    prev_to = from_ - timedelta(days=1)
    prev_from = prev_to - (to - from_)
    figures = sorted(SUMMARY_FIGURES.iter_values(), key=lambda f: (f.order, f.key))
    # ponytail: one query per figure and period, in sequence (one session). Batch them if the
    # figure count grows.
    return [
        SummaryCount(
            key=f.key,
            label=gettext(f.label),
            view=f.view,
            plugin=f.plugin,
            current=await f.count(session, from_, to),
            previous=await f.count(session, prev_from, prev_to),
        )
        for f in figures
    ]
