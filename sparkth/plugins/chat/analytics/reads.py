"""Read-side query over chat authoring activity.

Reads the ``chat_activity_daily`` continuous aggregate through ``read_rollup``; its ``dims``
must match the aggregate's ``dimension`` / ``outcome`` definition. Also declares chat's Overview
figures, which sum that read.
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import Bucket, Count, SummaryFigure, read_rollup
from sparkth.lib.i18n import gettext_noop
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


class ChatActivityPoint(BaseModel):
    """Count of one chat event type in one bucket. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    event_type: str
    dimension: str | None = None
    """Tool name for ``chat.tool_invoked``, failure cause for ``chat.turn_failed``."""
    outcome: str | None = None
    """``succeeded`` / ``failed`` for tool calls recorded with an outcome."""
    event_count: int


async def get_chat_activity(session: AsyncSession, from_: date, to: date, bucket: Bucket) -> list[ChatActivityPoint]:
    """Return chat event counts per ``bucket``, event type, dimension and outcome for ``from_``..``to``.

    Sparse: combinations with no events are omitted. Sorted with NULLs first, bytewise.
    """
    rows = await read_rollup(
        session,
        aggregate="chat_activity_daily",
        event_types=ACTIVITY_EVENT_TYPES,
        by_event_type=True,
        dims={
            "dimension": {ChatToolInvoked.event_type: "tool_name", ChatTurnFailed.event_type: "cause"},
            "outcome": "outcome",
        },
        count_column="event_count",
        from_=from_,
        to=to,
        bucket=bucket,
    )
    return [ChatActivityPoint.model_validate(dict(r)) for r in rows]


def _count_of(event_type: str) -> Count:
    async def count(session: AsyncSession, from_: date, to: date) -> int:
        # ponytail: each figure re-reads the aggregate; share one read if the Overview gets slow.
        rows = await get_chat_activity(session, from_, to, Bucket.month)
        return sum(r.event_count for r in rows if r.event_type == event_type)

    return count


# Built once so a second ChatPlugin() registers equal figures (a no-op).
SUMMARY_FIGURES_CHAT = (
    SummaryFigure(
        "chat.conversations",
        gettext_noop("Conversations started"),
        _count_of(ChatConversationStarted.event_type),
        view="authoring",
        order=40,
    ),
    SummaryFigure(
        "chat.messages",
        gettext_noop("Messages sent"),
        _count_of(ChatMessageSent.event_type),
        view="authoring",
        order=50,
    ),
    SummaryFigure(
        "chat.tool_calls", gettext_noop("Tool calls"), _count_of(ChatToolInvoked.event_type), view="authoring", order=60
    ),
    SummaryFigure(
        "chat.failed_turns",
        gettext_noop("Messages failed"),
        _count_of(ChatTurnFailed.event_type),
        view="authoring",
        order=70,
    ),
)
