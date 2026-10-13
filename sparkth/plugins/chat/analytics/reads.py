"""Read-side query over chat authoring activity.

PostgreSQL reads the ``chat_activity_daily`` continuous aggregate; SQLite (tests / e2e)
computes the same rows from ``raw_events``. The two must stay semantically identical: same
event types, same ``dimension`` / ``outcome`` extraction, UTC day bucketing, range filtered on
the day (inclusive both ends).
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import PG_BUCKET, SQLITE_BUCKET, Bucket, read_bucketed
from sparkth.plugins.chat.analytics.events import (
    ChatConversationStarted,
    ChatDocumentAttached,
    ChatDocumentDetached,
    ChatMessageSent,
    ChatToolInvoked,
    ChatTurnFailed,
)

ACTIVITY_EVENT_TYPES = (
    ChatConversationStarted.event_type,
    ChatMessageSent.event_type,
    ChatToolInvoked.event_type,
    ChatDocumentAttached.event_type,
    ChatDocumentDetached.event_type,
    ChatTurnFailed.event_type,
)
_IN_LIST = ", ".join(f"'{event_type}'" for event_type in ACTIVITY_EVENT_TYPES)


class ChatActivityPoint(BaseModel):
    """Count of one chat event type in one bucket. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    event_type: str
    dimension: str | None = None
    """Tool name for ``chat.tool_invoked``, failure cause for ``chat.turn_failed``."""
    outcome: str | None = None
    """``succeeded`` / ``failed`` for tool calls recorded with an outcome."""
    event_count: int


_PG_SQL = {
    bucket: text(
        f"SELECT to_char({expr}, 'YYYY-MM-DD') AS bucket, event_type, dimension, outcome, "
        "CAST(sum(event_count) AS bigint) AS event_count "
        "FROM chat_activity_daily "
        "WHERE (day AT TIME ZONE 'UTC')::date BETWEEN :from_ AND :to "
        "GROUP BY 1, event_type, dimension, outcome"
    )
    for bucket, expr in PG_BUCKET.items()
}
_SQLITE_SQL = {
    bucket: text(
        f"SELECT {expr} AS bucket, event_type, "
        "CASE event_type WHEN 'chat.tool_invoked' THEN json_extract(payload, '$.tool_name') "
        "WHEN 'chat.turn_failed' THEN json_extract(payload, '$.cause') END AS dimension, "
        "json_extract(payload, '$.outcome') AS outcome, count(*) AS event_count "
        "FROM raw_events "
        f"WHERE event_type IN ({_IN_LIST}) "
        "AND date(occurred_at) BETWEEN :from_ AND :to "
        "GROUP BY 1, 2, 3, 4"
    )
    for bucket, expr in SQLITE_BUCKET.items()
}


async def get_chat_activity(session: AsyncSession, from_: date, to: date, bucket: Bucket) -> list[ChatActivityPoint]:
    """Return chat event counts per ``bucket``, event type, dimension and outcome for ``from_``..``to``.

    Sparse: combinations with no events are omitted. Sorted in Python (NULLs first, bytewise)
    so both dialects return the same order.
    """
    rows = await read_bucketed(session, _PG_SQL, _SQLITE_SQL, from_, to, bucket)
    points = [ChatActivityPoint.model_validate(dict(row)) for row in rows]
    return sorted(points, key=lambda p: (p.bucket, p.event_type, p.dimension or "", p.outcome or ""))
