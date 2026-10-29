"""Read-side query over compose authoring activity.

Reads the ``compose_activity_daily`` continuous aggregate through ``read_rollup``; its ``dims``
must match the aggregate's ``dimension`` / ``outcome`` definition. Also declares compose's Overview
figures, which sum that read.
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import Bucket, Count, SummaryFigure, read_rollup
from sparkth.lib.i18n import gettext_noop
from sparkth.plugins.compose.analytics.events import (
    ComposeConversationStarted,
    ComposeDocumentAttached,
    ComposeDocumentDetached,
    ComposeMessageSent,
    ComposeRagSearchCompleted,
    ComposeToolInvoked,
    ComposeTurnFailed,
)

ACTIVITY_EVENT_TYPES = (
    ComposeConversationStarted.event_type,
    ComposeMessageSent.event_type,
    ComposeToolInvoked.event_type,
    ComposeDocumentAttached.event_type,
    ComposeDocumentDetached.event_type,
    ComposeTurnFailed.event_type,
    ComposeRagSearchCompleted.event_type,
)


class ComposeActivityPoint(BaseModel):
    """Count of one compose event type in one bucket. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    event_type: str
    dimension: str | None = None
    """Tool name for ``compose.tool_invoked``, failure cause for ``compose.turn_failed``,
    ``found`` / ``empty`` for ``compose.rag_search_completed``."""
    outcome: str | None = None
    """``succeeded`` / ``failed`` for tool calls recorded with an outcome."""
    event_count: int


async def get_compose_activity(
    session: AsyncSession, from_: date, to: date, bucket: Bucket
) -> list[ComposeActivityPoint]:
    """Return compose event counts per ``bucket``, event type, dimension and outcome for ``from_``..``to``.

    Sparse: combinations with no events are omitted. Sorted with NULLs first, bytewise.
    """
    rows = await read_rollup(
        session,
        aggregate="compose_activity_daily",
        event_types=ACTIVITY_EVENT_TYPES,
        by_event_type=True,
        dims={
            "dimension": {
                ComposeToolInvoked.event_type: "tool_name",
                ComposeTurnFailed.event_type: "cause",
                ComposeRagSearchCompleted.event_type: "result",
            },
            "outcome": "outcome",
        },
        count_column="event_count",
        from_=from_,
        to=to,
        bucket=bucket,
    )
    return [ComposeActivityPoint.model_validate(dict(r)) for r in rows]


def _count_of(event_type: str) -> Count:
    async def count(session: AsyncSession, from_: date, to: date) -> int:
        # ponytail: each figure re-reads the aggregate; share one read if the Overview gets slow.
        rows = await get_compose_activity(session, from_, to, Bucket.month)
        return sum(r.event_count for r in rows if r.event_type == event_type)

    return count


# Built once so a second ComposePlugin() registers equal figures (a no-op).
SUMMARY_FIGURES_COMPOSE = (
    SummaryFigure(
        "compose.conversations",
        gettext_noop("Conversations started"),
        _count_of(ComposeConversationStarted.event_type),
        view="authoring",
        order=40,
    ),
    SummaryFigure(
        "compose.messages",
        gettext_noop("Messages sent"),
        _count_of(ComposeMessageSent.event_type),
        view="authoring",
        order=50,
    ),
    SummaryFigure(
        "compose.tool_calls",
        gettext_noop("Tool calls"),
        _count_of(ComposeToolInvoked.event_type),
        view="authoring",
        order=60,
    ),
    SummaryFigure(
        "compose.failed_turns",
        gettext_noop("Messages failed"),
        _count_of(ComposeTurnFailed.event_type),
        view="authoring",
        order=70,
    ),
)
