"""Analytics events for the chat plugin — instructor course-authoring activity.

Chat is the course-authoring surface: instructors use it to generate courses, and
its tool registry exposes every other plugin's MCP tools
(``openedx_create_course_run``, ``canvas_create_quiz``, …). These events therefore
measure authoring *activity* (conversations, turns, completions) and authoring
*output* (tool executions) — not learner engagement.

Payloads carry identifiers, lengths, flags and names only. No message content,
conversation title, prompt, tool argument, or tool output ever enters an analytics
payload.

Every event carries ``occurred_at`` — when the thing happened, taken from the row that
records it — while ``received_at`` is stamped by the database when the row lands. The two
differ by however long the emission took, which for a streamed turn is the length of the
stream, so order these events by ``occurred_at`` and read ``received_at`` only as a measure
of that lag.

Known gap
---------

**Dropped events.** Events queued on ``background_tasks`` are discarded when the
route raises — the 502 and 500 handlers — and a client disconnecting mid-stream
yields a ``chat.completion_served`` with no ``chat.conversation_started`` or
``chat.message_sent``. The conversation and message rows are committed regardless, so
these counts are lower bounds: failed turns are systematically under-counted.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks
from pydantic import NonNegativeInt

from sparkth.lib.analytics import AnalyticsEventSchema, PendingEvent, emit_event, emit_events
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.tools import get_tool_registry

logger = get_logger(__name__)


class ChatConversationStarted(AnalyticsEventSchema):
    """A new authoring conversation was created."""

    event_type = "chat.conversation_started"
    version = 1

    conversation_id: str
    provider: str
    model: str


class ChatMessageSent(AnalyticsEventSchema):
    """An instructor turn was persisted.

    ``message_length`` is the character count of the *stored* message row, which is
    the only place a request's content blocks are flattened into text. On a turn that
    carries attachments but no text the stored body is the placeholder
    ``"[Document attachment]"``, so such a turn records that placeholder's length
    rather than zero. The count is non-negative, so a producer bug fails validation
    here instead of landing a row that skews every aggregate built on it.

    ``has_attachment`` reflects only an inline upload on the turn itself. Documents
    attached to the conversation by ``document_ids`` do not set it.
    """

    event_type = "chat.message_sent"
    version = 1

    conversation_id: str
    provider: str
    model: str
    message_length: NonNegativeInt
    has_attachment: bool


class ChatCompletionServed(AnalyticsEventSchema):
    """A completion the LLM actually produced was served.

    Not every delivered assistant reply emits this. Two streaming branches persist and
    deliver a reply without one, because no LLM completion was generated: the
    RAG-no-results branch, which answers with a fixed "nothing matched your query"
    message, and the streaming-error branch, which stores the provider failure as an
    ``is_error`` assistant message.

    ``rag_used`` records that the intent router *decided* to retrieve, not that
    retrieval returned anything. ``tool_call_count`` counts executions attempted,
    and is non-negative so a producer bug fails validation rather than skewing
    every aggregate built on it.
    """

    event_type = "chat.completion_served"
    version = 1

    conversation_id: str
    provider: str
    model: str
    streamed: bool
    rag_used: bool
    tool_call_count: NonNegativeInt


class ChatToolInvoked(AnalyticsEventSchema):
    """One tool execution — the authoring-output event.

    Grouping by ``tool_name`` answers what was authored; by ``tool_category``,
    which LMS. Counts attempted executions, so this is not proof the authoring
    action succeeded.
    """

    event_type = "chat.tool_invoked"
    version = 1

    conversation_id: str
    tool_name: str
    tool_category: str


@dataclass(frozen=True)
class AnalyticsAttribution:
    """Who acted, and through which provider — the only completion facts a seam
    cannot work out from its own state.

    The stream processor already holds the model it is streaming from
    (``provider.model``) and whether RAG ran (``rag_search_required``); handing it
    those again would be two sources of truth for one fact. It has no way to know the
    provider's *name* or the acting user, though: its ``user_id`` is populated only
    when RAG runs, so reading the actor off it would drop them from most events.
    """

    provider: str
    actor_id: str


# The two completion paths report executions under different keys: the streaming
# path's tool_end events yield {"name": …}, while the non-streaming provider records
# {"tool": …, "tool_input": …, "output": …}. Both are read here so the mapping exists
# in exactly one place.
_TOOL_NAME_KEYS = ("name", "tool")


def _record_name(record: dict[str, Any]) -> str | None:
    """Return the first non-empty string found under either path's name key."""
    for key in _TOOL_NAME_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def tool_names(records: list[dict[str, Any]]) -> list[str]:
    """Extract tool names from either completion path's execution records.

    Order and duplicates are preserved: two executions of the same tool are two
    authoring actions. Records with no usable name are dropped rather than raising —
    a malformed record must not cost the whole completion's analytics — but the drop
    is logged, because a renamed key on either path would otherwise zero tool
    analytics with no trace.

    Only the name is read, and only the *keys* of an unusable record are logged.
    ``tool_input`` and ``output`` can contain course content and learner-identifying
    data, and must never reach an analytics payload or a log line.
    """
    names: list[str] = []
    for record in records:
        name = _record_name(record)
        if name is None:
            logger.warning(
                "Dropping a chat tool execution record with no usable name key; keys present: %s",
                sorted(record),
            )
            continue
        names.append(name)
    return names


async def _emit(event: AnalyticsEventSchema, actor_id: str, occurred_at: datetime) -> None:
    """Hand one already-constructed event to the emission primitive.

    The payload is dumped from the event rather than hand-listed at each call site,
    so a field added to a schema cannot be silently omitted: the constructor call
    fails type-checking instead of the analytics write failing at runtime. The
    ``event_type``/``version`` identity travels with the instance for the same reason.
    ``ClassVar`` keeps both out of the dumped payload.

    ``occurred_at`` is required rather than defaulted as defaulting
    to now would stamp a whole turn's events at the end of it and lose their order.
    """
    await emit_event(
        event.event_type,
        event.version,
        event.model_dump(mode="json"),
        actor_id=actor_id,
        occurred_at=occurred_at,
    )


async def emit_conversation_started(
    conversation_id: str, provider: str, model: str, actor_id: str, occurred_at: datetime
) -> None:
    """Emit ``chat.conversation_started``, timed by when the conversation row was created."""
    await _emit(
        ChatConversationStarted(
            conversation_id=conversation_id,
            provider=provider,
            model=model,
        ),
        actor_id,
        occurred_at,
    )


async def emit_message_sent(
    conversation_id: str,
    provider: str,
    model: str,
    message_length: int,
    has_attachment: bool,
    actor_id: str,
    occurred_at: datetime,
) -> None:
    """Emit ``chat.message_sent`` for one instructor turn, timed by when it was stored."""
    await _emit(
        ChatMessageSent(
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            message_length=message_length,
            has_attachment=has_attachment,
        ),
        actor_id,
        occurred_at,
    )


async def emit_completion(
    conversation_id: str,
    attribution: AnalyticsAttribution,
    model: str,
    rag_used: bool,
    streamed: bool,
    executed_tools: list[str],
    occurred_at: datetime,
) -> None:
    """Emit one completion and one ``chat.tool_invoked`` per tool it executed.

    The whole group goes through a single :func:`emit_events` call so the completion
    and its tool events share one analytics session. Emitting them one at a time cost
    a session per event, and — because they land in sequence — a failed completion
    write dropped every tool event behind it.

    ``streamed`` is passed by the seam rather than derived, because it is the one
    fact determined by *which* seam emits. Tool categories are resolved from the
    registry here so no call site has to know that LangChain tools carry none.
    """
    events = [
        ChatCompletionServed(
            conversation_id=conversation_id,
            provider=attribution.provider,
            model=model,
            streamed=streamed,
            rag_used=rag_used,
            tool_call_count=len(executed_tools),
        ),
        *(
            ChatToolInvoked(
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_category=get_tool_registry().category_for(tool_name),
            )
            for tool_name in executed_tools
        ),
    ]
    await emit_events(
        [
            PendingEvent(
                event_type=event.event_type,
                version=event.version,
                payload=event.model_dump(mode="json"),
                actor_id=attribution.actor_id,
                occurred_at=occurred_at,
            )
            for event in events
        ]
    )


@dataclass(frozen=True)
class ChatTurnAnalytics:
    """The scheduling surface for one request's chat events.

    Built once, from the facts every chat event of a turn shares, and handed the
    request's background queue. Each ``schedule_*`` method queues exactly one event,
    so a route seam names what happened and nothing else: the shared identity, the
    per-event payload and the fact that emission is deferred all live here rather
    than being spelled out at four call sites.

    **Queued, never awaited.** These helpers construct their schemas, and
    ``message_length`` and ``tool_call_count`` are ``NonNegativeInt``, so
    construction itself can raise ``ValidationError``; emission propagates every
    failure by design. Both only reach a caller safely once the response is flushed,
    which is what the background queue guarantees.

    **Queue analytics after functional background work.** Starlette runs the queue as
    a plain sequential loop with no per-task isolation, so an emit queued ahead of
    real work lets an analytics outage silently stop that work. The methods here
    cannot enforce that — only the order a route calls them in can.
    """

    background_tasks: BackgroundTasks
    conversation_id: str
    provider: str
    model: str
    actor_id: str

    def schedule_conversation_started(self, *, occurred_at: datetime) -> None:
        """Queue ``chat.conversation_started`` — the create branch only.

        A conversation resolved by uuid has already been started, and re-emitting
        would make every continued turn look like a new conversation.
        """
        self.background_tasks.add_task(
            emit_conversation_started,
            conversation_id=self.conversation_id,
            provider=self.provider,
            model=self.model,
            actor_id=self.actor_id,
            occurred_at=occurred_at,
        )

    def schedule_message_sent(self, *, message_length: int, has_attachment: bool, occurred_at: datetime) -> None:
        """Queue ``chat.message_sent`` for one instructor turn."""
        self.background_tasks.add_task(
            emit_message_sent,
            conversation_id=self.conversation_id,
            provider=self.provider,
            model=self.model,
            message_length=message_length,
            has_attachment=has_attachment,
            actor_id=self.actor_id,
            occurred_at=occurred_at,
        )

    def schedule_completion(
        self, *, rag_used: bool, streamed: bool, executed_tools: list[str], occurred_at: datetime
    ) -> None:
        """Queue the completion and its tool events as one task.

        One task, not one per event: they land through a single analytics session,
        and a caller cannot queue the completion and forget the tools it executed.
        """
        self.background_tasks.add_task(
            emit_completion,
            conversation_id=self.conversation_id,
            attribution=self.attribution,
            model=self.model,
            rag_used=rag_used,
            streamed=streamed,
            executed_tools=executed_tools,
            occurred_at=occurred_at,
        )

    @property
    def attribution(self) -> AnalyticsAttribution:
        """The two facts a seam emitting for itself cannot derive.

        The streaming seam emits from inside its own detached task rather than from
        this queue, so it takes these and works out the rest from its own state.
        """
        return AnalyticsAttribution(provider=self.provider, actor_id=self.actor_id)
