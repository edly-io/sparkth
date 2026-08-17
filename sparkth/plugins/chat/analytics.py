"""Analytics events for the chat plugin — instructor course-authoring activity.

Chat is the course-authoring surface: instructors use it to generate courses, and
its tool registry exposes every other plugin's MCP tools
(``openedx_create_course_run``, ``canvas_create_quiz``, …). These events therefore
measure authoring *activity* (conversations, turns, completions) and authoring
*output* (tool executions) — not learner engagement.

Payloads carry identifiers, lengths, flags and names only. No message content,
conversation title, prompt, tool argument, or tool output ever enters an analytics
payload.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import NonNegativeInt

from sparkth.lib.analytics import AnalyticsEventSchema, emit_event
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
    """An instructor turn was persisted. ``message_length`` is a character count.

    The count is non-negative, so a producer bug fails validation here instead of
    landing a row that skews every aggregate built on it.
    """

    event_type = "chat.message_sent"
    version = 1

    conversation_id: str
    provider: str
    model: str
    message_length: NonNegativeInt
    has_attachment: bool


class ChatCompletionServed(AnalyticsEventSchema):
    """An assistant reply was delivered.

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
class CompletionAnalyticsContext:
    """Completion facts the route owns, passed to whichever seam emits.

    ``model`` is the model actually used, which can differ from the conversation's
    stored model when the request sets ``model_override``. ``actor_id`` travels here
    rather than being read off the stream processor, whose ``user_id`` is only
    populated when RAG runs.
    """

    provider: str
    model: str
    rag_used: bool
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


async def _emit(event: AnalyticsEventSchema, actor_id: str) -> None:
    """Hand one already-constructed event to the emission primitive.

    The payload is dumped from the event rather than hand-listed at each call site,
    so a field added to a schema cannot be silently omitted: the constructor call
    fails type-checking instead of the analytics write failing at runtime. The
    ``event_type``/``version`` identity travels with the instance for the same reason.
    ``ClassVar`` keeps both out of the dumped payload.
    """
    await emit_event(event.event_type, event.version, event.model_dump(mode="json"), actor_id=actor_id)


async def emit_conversation_started(conversation_id: str, provider: str, model: str, actor_id: str) -> None:
    """Emit ``chat.conversation_started``."""
    await _emit(
        ChatConversationStarted(
            conversation_id=conversation_id,
            provider=provider,
            model=model,
        ),
        actor_id,
    )


async def emit_message_sent(
    conversation_id: str,
    provider: str,
    model: str,
    message_length: int,
    has_attachment: bool,
    actor_id: str,
) -> None:
    """Emit ``chat.message_sent`` for one instructor turn."""
    await _emit(
        ChatMessageSent(
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            message_length=message_length,
            has_attachment=has_attachment,
        ),
        actor_id,
    )


async def emit_completion_served(
    conversation_id: str,
    context: CompletionAnalyticsContext,
    tool_call_count: int,
    streamed: bool,
) -> None:
    """Emit ``chat.completion_served``.

    ``streamed`` is passed by the seam rather than read from the context, because it
    is the one fact determined by *which* seam emits.
    """
    await _emit(
        ChatCompletionServed(
            conversation_id=conversation_id,
            provider=context.provider,
            model=context.model,
            streamed=streamed,
            rag_used=context.rag_used,
            tool_call_count=tool_call_count,
        ),
        context.actor_id,
    )


async def emit_tool_invoked(conversation_id: str, tool_name: str, actor_id: str) -> None:
    """Emit ``chat.tool_invoked`` for one tool execution.

    The category is resolved from the tool registry here so no call site has to
    know that LangChain tools carry no category.
    """
    await _emit(
        ChatToolInvoked(
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_category=get_tool_registry().category_for(tool_name),
        ),
        actor_id,
    )
