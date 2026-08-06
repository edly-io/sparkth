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

from sparkth.lib.analytics import AnalyticsEventSchema, emit_event
from sparkth.plugins.chat.tools import get_tool_registry


class ChatConversationStarted(AnalyticsEventSchema):
    """A new authoring conversation was created."""

    event_type = "chat.conversation_started"
    version = 1

    conversation_id: str
    provider: str
    model: str


class ChatMessageSent(AnalyticsEventSchema):
    """An instructor turn was persisted. ``message_length`` is a character count."""

    event_type = "chat.message_sent"
    version = 1

    conversation_id: str
    provider: str
    model: str
    message_length: int
    has_attachment: bool


class ChatCompletionServed(AnalyticsEventSchema):
    """An assistant reply was delivered.

    ``rag_used`` records that the intent router *decided* to retrieve, not that
    retrieval returned anything. ``tool_call_count`` counts executions attempted.
    """

    event_type = "chat.completion_served"
    version = 1

    conversation_id: str
    provider: str
    model: str
    streamed: bool
    rag_used: bool
    tool_call_count: int


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


def tool_names(records: list[dict[str, Any]]) -> list[str]:
    """Extract tool names from either completion path's execution records.

    Order and duplicates are preserved: two executions of the same tool are two
    authoring actions. Records with no usable name are dropped rather than raising —
    a malformed record must not cost the whole completion's analytics.

    Only the name is read. ``tool_input`` and ``output`` can contain course content
    and learner-identifying data, and must never reach an analytics payload.
    """
    names: list[str] = []
    for record in records:
        for key in _TOOL_NAME_KEYS:
            value = record.get(key)
            if isinstance(value, str) and value:
                names.append(value)
                break
    return names


async def emit_conversation_started(conversation_id: str, provider: str, model: str, actor_id: str) -> None:
    """Emit ``chat.conversation_started``."""
    await emit_event(
        ChatConversationStarted.event_type,
        ChatConversationStarted.version,
        {"conversation_id": conversation_id, "provider": provider, "model": model},
        actor_id=actor_id,
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
    await emit_event(
        ChatMessageSent.event_type,
        ChatMessageSent.version,
        {
            "conversation_id": conversation_id,
            "provider": provider,
            "model": model,
            "message_length": message_length,
            "has_attachment": has_attachment,
        },
        actor_id=actor_id,
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
    await emit_event(
        ChatCompletionServed.event_type,
        ChatCompletionServed.version,
        {
            "conversation_id": conversation_id,
            "provider": context.provider,
            "model": context.model,
            "streamed": streamed,
            "rag_used": context.rag_used,
            "tool_call_count": tool_call_count,
        },
        actor_id=context.actor_id,
    )


async def emit_tool_invoked(conversation_id: str, tool_name: str, actor_id: str) -> None:
    """Emit ``chat.tool_invoked`` for one tool execution.

    The category is resolved from the tool registry here so no call site has to
    know that LangChain tools carry no category.
    """
    await emit_event(
        ChatToolInvoked.event_type,
        ChatToolInvoked.version,
        {
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "tool_category": get_tool_registry().category_for(tool_name),
        },
        actor_id=actor_id,
    )
