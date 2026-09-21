"""The chat plugin's analytics event schemas.

Payloads carry identifiers, lengths, flags and names only: no message content, title,
prompt, tool argument or tool output.
"""

from enum import StrEnum
from typing import Literal

from pydantic import NonNegativeInt

from sparkth.lib.analytics import AnalyticsEventSchema


class ChatConversationStarted(AnalyticsEventSchema):
    """A new authoring conversation was created."""

    event_type = "chat.conversation_started"
    version = 1

    conversation_id: str
    provider: str
    model: str


class ChatMessageSent(AnalyticsEventSchema):
    """An instructor turn was persisted.

    ``message_length`` counts the stored row, so a text-less turn records the length of
    the ``"[Document attachment]"`` placeholder rather than zero.
    ``has_attachment`` covers an inline upload only, not documents attached by
    ``document_ids``.
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

    Not every delivered reply emits this: the RAG-no-results and streaming-error branches
    reply without an LLM completion.
    ``rag_used`` means retrieval was *decided on*, not that it returned anything.
    ``tool_call_count`` counts attempts.
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

    Counts attempts, so it is not proof the authoring action succeeded.
    """

    event_type = "chat.tool_invoked"
    version = 1

    conversation_id: str
    tool_name: str
    tool_category: str


class ChatDocumentAttached(AnalyticsEventSchema):
    """An instructor put a document in play for a conversation.

    ``source`` separates a deliberate attach from one named on a completion request.
    Re-attaching an already-attached document emits nothing.
    """

    event_type = "chat.document_attached"
    version = 1

    conversation_id: str
    document_id: int
    source: Literal["explicit", "completion_request"]


class ChatDocumentDetached(AnalyticsEventSchema):
    """An instructor removed a document from a conversation.

    ``seconds_attached`` is measured from the removed row's ``attached_at`` — the one fact
    about it that outlives the row.
    """

    event_type = "chat.document_detached"
    version = 1

    conversation_id: str
    document_id: int
    seconds_attached: NonNegativeInt


class ChatDocumentsSkipped(AnalyticsEventSchema):
    """A completion request named documents that were silently dropped from the turn.

    Counts only, never ids: a skipped id may belong to another user.
    """

    event_type = "chat.documents_skipped"
    version = 1

    conversation_id: str
    requested_count: NonNegativeInt
    skipped_count: NonNegativeInt


class ChatAttachmentUnusable(AnalyticsEventSchema):
    """A turn ran while an attached document was not ingestible, so it was ignored.

    Chat reads only READY attachments, so the instructor gets a reply that ignores their
    file. Emitted once per unusable document per turn; re-emitting across turns is
    intended.
    """

    event_type = "chat.attachment_unusable"
    version = 1

    conversation_id: str
    document_id: int
    status: Literal["queued", "processing", "failed", "deleted"]


class ScopeVerdict(StrEnum):
    """What the scope classifier decided about one turn."""

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    NOT_JUDGED = "not_judged"


class ChatScopeClassified(AnalyticsEventSchema):
    """The scope classifier judged one turn.

    ``out_of_scope`` is a refusal — the chat model is never reached, and this event is the
    only record of it. Emitted on every classification, so the rate has its denominator
    here; ``not_judged`` is the fail-open path.
    ``conversation_id`` is null on a first message, judged before the conversation exists.
    ``classifier_model`` is the classifier's own model, not the conversation's.
    """

    event_type = "chat.scope_classified"
    version = 1

    conversation_id: str | None
    provider: str
    classifier_model: str
    verdict: ScopeVerdict
    history_turns: NonNegativeInt
    attachment_count: NonNegativeInt
    query_length: NonNegativeInt


class ChatRagSearchClassified(AnalyticsEventSchema):
    """The search classifier decided whether a turn needed the attached documents.

    Emitted only when the classifier was consulted, so its absence means there was no
    decision to make — not that retrieval was skipped.
    ``requires_search=False`` means attached documents were deliberately not read.
    ``documents_with_unreadable_structure`` counts failed heading lookups, not documents
    that genuinely have no sections.
    A failed classification is fatal to the turn and lands as ``chat.turn_failed`` instead.
    """

    event_type = "chat.rag_search_classified"
    version = 1

    conversation_id: str
    provider: str
    classifier_model: str
    requires_search: bool
    document_count: NonNegativeInt
    documents_with_unreadable_structure: NonNegativeInt


class TurnFailureCause(StrEnum):
    """Why a turn ended in an error message instead of a reply.

    A closed set on purpose: the exception's own text can quote a prompt or a document, so
    the cause is named from here rather than carried from the error.
    """

    LLM_CONFIG_UNUSABLE = "llm_config_unusable"
    PROVIDER_API_ERROR = "provider_api_error"
    RAG_SEARCH_ERROR = "rag_search_error"
    RAG_RETRIEVAL_ERROR = "rag_retrieval_error"
    UNEXPECTED = "unexpected"


class ChatTurnFailed(AnalyticsEventSchema):
    """A turn ended in an error message instead of a reply.

    ``provider`` and ``model`` are null only for ``llm_config_unusable``, where neither has
    resolved yet. ``conversation_id`` is null when the turn failed before a conversation
    existed.
    """

    event_type = "chat.turn_failed"
    version = 1

    conversation_id: str | None
    provider: str | None
    model: str | None
    cause: TurnFailureCause
    streamed: bool
