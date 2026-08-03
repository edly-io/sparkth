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

from sparkth.lib.analytics import AnalyticsEventSchema


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
