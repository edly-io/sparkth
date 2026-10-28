"""Bucket SQL and day ranges shared by the analytics reads.

Day boundaries are UTC on both dialects. ``PG_BUCKET`` and ``SQLITE_BUCKET`` reduce a timestamp to
its bucket's first day, keyed by :class:`Bucket` so no request input ever reaches the SQL.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sparkth.core.analytics.models import raw_events
from sparkth.core.analytics.reads.enums import Bucket

# Per-bucket SQL that reduces a timestamp to its bucket's first day (the day, its Monday, or the
# 1st), keyed by the enum so no request input ever reaches the SQL.
# PG: date_trunc('week') starts on Monday. SQLite: 'weekday 0' moves to the next Sunday
# (or stays on one), and '-6 days' steps back to that week's Monday.
PG_BUCKET = {
    Bucket.day: "day AT TIME ZONE 'UTC'",
    Bucket.week: "date_trunc('week', day AT TIME ZONE 'UTC')",
    Bucket.month: "date_trunc('month', day AT TIME ZONE 'UTC')",
}
# The same buckets over raw_events.occurred_at, for queries that read raw events on PostgreSQL.
PG_RAW_BUCKET = {
    Bucket.day: "date_trunc('day', occurred_at AT TIME ZONE 'UTC')",
    Bucket.week: "date_trunc('week', occurred_at AT TIME ZONE 'UTC')",
    Bucket.month: "date_trunc('month', occurred_at AT TIME ZONE 'UTC')",
}
SQLITE_BUCKET = {
    Bucket.day: "date(occurred_at)",
    Bucket.week: "date(occurred_at, 'weekday 0', '-6 days')",
    Bucket.month: "strftime('%Y-%m-01', occurred_at)",
}


def in_days(from_: date, to: date) -> tuple[Any, Any]:
    """``raw_events`` conditions for days ``from_``..``to`` (inclusive, UTC).

    A datetime range, not ``date(occurred_at)``, so one query serves both dialects.
    """
    start = datetime.combine(from_, time(), timezone.utc)
    end = datetime.combine(to + timedelta(days=1), time(), timezone.utc)
    return raw_events.c.occurred_at >= start, raw_events.c.occurred_at < end
