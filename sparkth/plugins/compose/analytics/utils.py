"""Emission helpers and the per-request scheduling surfaces.

Order events by ``occurred_at`` (when it happened), not ``received_at`` (when the row
landed).

Known gap: events queued on ``background_tasks`` are dropped when the route raises, so
those counts are lower bounds. ``compose.message_sent`` and ``compose.turn_failed`` go out on
detached tasks instead, so a failed turn still counts both its message and its failure.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, NamedTuple

from fastapi import BackgroundTasks

from sparkth.lib.analytics import AnalyticsEventSchema, PendingEvent, emit_event, emit_events
from sparkth.lib.audit import ToolFailureKind
from sparkth.lib.log import get_logger
from sparkth.plugins.compose.analytics.events import (
    ComposeAttachmentUnusable,
    ComposeCompletionServed,
    ComposeConversationStarted,
    ComposeDocumentAttached,
    ComposeDocumentDetached,
    ComposeDocumentsSkipped,
    ComposeMessageSent,
    ComposeRagSearchClassified,
    ComposeRagSearchCompleted,
    ComposeScopeClassified,
    ComposeToolInvoked,
    ComposeTurnFailed,
    ScopeVerdict,
    SearchResult,
    StopPoint,
    ToolOutcome,
    TurnFailureCause,
)
from sparkth.plugins.compose.detached import detach
from sparkth.plugins.compose.tools import get_tool_registry

logger = get_logger(__name__)


AnalyticsEventBuilder = Callable[[], AnalyticsEventSchema]


@dataclass(frozen=True)
class AnalyticsAttribution:
    """Who acted, and through which provider.

    The only completion facts a self-emitting seam cannot derive from its own state.
    """

    provider: str
    actor_id: str


# The two completion paths report executions under different keys: the streaming
# path records {"name": …, "failure": …} from its tool_end events, while the non-streaming
# provider records {"tool": …, "tool_input": …, "output": …, "failure": …}. Both are read
# here so the mapping exists in exactly one place.
_TOOL_NAME_KEYS = ("name", "tool")


def _record_name(record: dict[str, Any]) -> str | None:
    """Return the first non-empty string found under either path's name key."""
    for key in _TOOL_NAME_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


class ExecutedTool(NamedTuple):
    """One tool execution: its name and how it failed, or ``None`` if it succeeded."""

    name: str
    failure: ToolFailureKind | None


def executed_tools_from(records: list[dict[str, Any]]) -> list[ExecutedTool]:
    """Read the executed tools from either completion path's execution records.

    Order and duplicates are preserved — two executions are two authoring actions. An
    unusable record is dropped and logged rather than raising.

    Only the name and failure are read, and only the *keys* of a bad record are logged:
    ``tool_input`` and ``output`` can hold course content and must never reach a payload or
    a log line.
    """
    executed: list[ExecutedTool] = []
    for record in records:
        name = _record_name(record)
        if name is None:
            logger.warning(
                "Dropping a chat tool execution record with no usable name key; keys present: %s",
                sorted(record),
            )
            continue
        executed.append(ExecutedTool(name, record.get("failure")))
    return executed


async def _emit(build: AnalyticsEventBuilder, actor_id: str, occurred_at: datetime) -> None:
    """Build one event and hand it to the emission primitive.

    ``occurred_at`` is required, not defaulted: defaulting would stamp a whole turn's
    events at the end of it and lose their order.
    """
    event = build()
    await emit_event(
        event.event_type,
        event.version,
        event.model_dump(mode="json"),
        actor_id=actor_id,
        occurred_at=occurred_at,
    )


def as_utc(value: datetime) -> datetime:
    """Read a stored timestamp as UTC-aware; SQLite returns a ``timezone=True`` column naive."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def rag_search_event(
    conversation_id: str, provider: str, *, chunks_found: int, document_count: int, streamed: bool
) -> ComposeRagSearchCompleted:
    """Build ``compose.rag_search_completed``; ``result`` follows from ``chunks_found``."""
    return ComposeRagSearchCompleted(
        conversation_id=conversation_id,
        provider=provider,
        result=SearchResult.EMPTY if chunks_found == 0 else SearchResult.FOUND,
        chunks_found=chunks_found,
        document_count=document_count,
        streamed=streamed,
    )


async def emit_rag_search_completed(event: ComposeRagSearchCompleted, actor_id: str, occurred_at: datetime) -> None:
    """Emit a search the streaming seam recorded. Await it outside every guard."""
    await _emit(lambda: event, actor_id, occurred_at)


async def emit_documents_detached(
    detachments: list[tuple[str, int]],
    document_id: int,
    actor_id: str,
    occurred_at: datetime,
) -> None:
    """Emit one ``compose.document_detached`` per conversation the document was removed from."""
    events = [
        ComposeDocumentDetached(
            conversation_id=conversation_id,
            document_id=document_id,
            seconds_attached=seconds_attached,
        )
        for conversation_id, seconds_attached in detachments
    ]
    await emit_events(
        [
            PendingEvent(
                event_type=event.event_type,
                version=event.version,
                payload=event.model_dump(mode="json"),
                actor_id=actor_id,
                occurred_at=occurred_at,
            )
            for event in events
        ]
    )


async def emit_completion(
    conversation_id: str,
    attribution: AnalyticsAttribution,
    model: str,
    rag_used: bool,
    streamed: bool,
    executed_tools: list[ExecutedTool],
    occurred_at: datetime,
    stopped_at: StopPoint | None = None,
) -> None:
    """Emit one completion and one ``compose.tool_invoked`` per tool it executed.

    One :func:`emit_events` call, so the group shares a session and a failed completion
    write cannot drop the tool events behind it.
    """
    events = [
        ComposeCompletionServed(
            conversation_id=conversation_id,
            provider=attribution.provider,
            model=model,
            streamed=streamed,
            rag_used=rag_used,
            tool_call_count=len(executed_tools),
            stopped_at=stopped_at,
        ),
        *(
            ComposeToolInvoked(
                conversation_id=conversation_id,
                tool_name=tool.name,
                tool_category=get_tool_registry().category_for(tool.name),
                outcome=ToolOutcome.SUCCEEDED if tool.failure is None else ToolOutcome.FAILED,
                failure_kind=tool.failure,
            )
            for tool in executed_tools
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
class ComposeTurnAnalytics:
    """The scheduling surface for one request's compose events.

    Built once from the facts a turn's events share; each ``schedule_*`` sends exactly
    one event and never awaits. All but ``schedule_message_sent`` queue it on
    ``background_tasks``; that one detaches it.

    **Queue analytics after functional background work.** Starlette runs the queue as one
    sequential loop, so an emit queued ahead of real work lets an analytics outage stop
    that work. Only the calling order can enforce this.
    """

    background_tasks: BackgroundTasks
    conversation_id: str
    provider: str
    model: str
    actor_id: str

    def schedule_conversation_started(self, *, occurred_at: datetime) -> None:
        """Queue ``compose.conversation_started`` — the create branch only, or every continued
        turn would look like a new conversation."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeConversationStarted(
                conversation_id=self.conversation_id, provider=self.provider, model=self.model
            ),
            self.actor_id,
            occurred_at,
        )

    def schedule_message_sent(self, *, message_length: int, has_attachment: bool, occurred_at: datetime) -> None:
        """Send ``compose.message_sent`` for one stored instructor turn, on a detached task.

        Not ``background_tasks``: the turn's route can still raise after the message is
        stored, which discards that queue, and a failed turn must count its message for the
        failure rate to mean anything. The message is already committed, so the event is
        true either way. Nothing awaits or catches it.
        """
        detach(
            _emit(
                lambda: ComposeMessageSent(
                    conversation_id=self.conversation_id,
                    provider=self.provider,
                    model=self.model,
                    message_length=message_length,
                    has_attachment=has_attachment,
                ),
                self.actor_id,
                occurred_at,
            )
        )

    def schedule_completion(
        self, *, rag_used: bool, streamed: bool, executed_tools: list[ExecutedTool], occurred_at: datetime
    ) -> None:
        """Queue the completion and its tool events as one task, through one session."""
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

    def schedule_rag_search_completed(self, *, chunks_found: int, document_count: int, occurred_at: datetime) -> None:
        """Queue ``compose.rag_search_completed`` for a non-streamed search that returned."""
        self.background_tasks.add_task(
            _emit,
            lambda: rag_search_event(
                self.conversation_id,
                self.provider,
                chunks_found=chunks_found,
                document_count=document_count,
                streamed=False,
            ),
            self.actor_id,
            occurred_at,
        )

    @property
    def attribution(self) -> AnalyticsAttribution:
        """The two facts a self-emitting seam cannot derive; the streaming seam takes these."""
        return AnalyticsAttribution(provider=self.provider, actor_id=self.actor_id)


@dataclass(frozen=True)
class ComposeAttachmentAnalytics:
    """The scheduling surface for one conversation's document events.

    A sibling to :class:`ComposeTurnAnalytics`: these describe what happened to a
    conversation's *documents*, not to a turn, so they carry no provider or model. Same
    contract — every method queues and takes the moment its event happened.
    """

    background_tasks: BackgroundTasks
    conversation_id: str
    actor_id: str

    def schedule_document_attached(
        self, *, document_id: int, source: Literal["explicit", "completion_request"], occurred_at: datetime
    ) -> None:
        """Queue ``compose.document_attached``. Only for a row that was actually created."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeDocumentAttached(
                conversation_id=self.conversation_id, document_id=document_id, source=source
            ),
            self.actor_id,
            occurred_at,
        )

    def schedule_document_detached(self, *, document_id: int, seconds_attached: int, occurred_at: datetime) -> None:
        """Queue ``compose.document_detached``. Only when a row was actually removed."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeDocumentDetached(
                conversation_id=self.conversation_id,
                document_id=document_id,
                seconds_attached=seconds_attached,
            ),
            self.actor_id,
            occurred_at,
        )

    def schedule_documents_skipped(self, *, requested_count: int, skipped_count: int, occurred_at: datetime) -> None:
        """Queue ``compose.documents_skipped``. Only when something was actually skipped."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeDocumentsSkipped(
                conversation_id=self.conversation_id,
                requested_count=requested_count,
                skipped_count=skipped_count,
            ),
            self.actor_id,
            occurred_at,
        )

    def schedule_attachment_unusable(
        self,
        *,
        document_id: int,
        status: Literal["queued", "processing", "failed", "deleted"],
        occurred_at: datetime,
    ) -> None:
        """Queue ``compose.attachment_unusable`` for one document this turn could not use."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeAttachmentUnusable(
                conversation_id=self.conversation_id, document_id=document_id, status=status
            ),
            self.actor_id,
            occurred_at,
        )


def record_turn_failed(
    *,
    conversation_id: str | None,
    provider: str | None,
    model: str | None,
    cause: TurnFailureCause,
    streamed: bool,
    actor_id: str,
) -> None:
    """Record a failed turn from a seam that is about to raise.

    On a detached task, not ``background_tasks``: that queue hangs off a response the
    endpoint returns, and these seams raise instead, so a queued emit would be discarded on
    exactly the paths this event exists for. Nothing awaits or catches it.

    ``occurred_at`` is stamped here — the failure leaves no row that records when it happened.
    """
    detach(
        _emit(
            lambda: ComposeTurnFailed(
                conversation_id=conversation_id,
                provider=provider,
                model=model,
                cause=cause,
                streamed=streamed,
            ),
            actor_id,
            datetime.now(timezone.utc),
        )
    )


@dataclass(frozen=True)
class ComposeClassifierAnalytics:
    """The scheduling surface for the classifier decisions.

    Built before the first scope check, which happens before the conversation exists.
    Carries the provider but no model: each classifier passes its own per call.
    """

    background_tasks: BackgroundTasks
    provider: str
    actor_id: str

    def schedule_scope_classified(
        self,
        *,
        conversation_id: str | None,
        classifier_model: str,
        verdict: ScopeVerdict,
        history_turns: int,
        attachment_count: int,
        query_length: int,
        occurred_at: datetime,
    ) -> None:
        """Queue ``compose.scope_classified``. Exactly once per turn."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeScopeClassified(
                conversation_id=conversation_id,
                provider=self.provider,
                classifier_model=classifier_model,
                verdict=verdict,
                history_turns=history_turns,
                attachment_count=attachment_count,
                query_length=query_length,
            ),
            self.actor_id,
            occurred_at,
        )

    def schedule_rag_search_classified(
        self,
        *,
        conversation_id: str,
        classifier_model: str,
        requires_search: bool,
        document_count: int,
        documents_with_unreadable_structure: int,
        occurred_at: datetime,
    ) -> None:
        """Queue ``compose.rag_search_classified``. Only when the classifier was consulted."""
        self.background_tasks.add_task(
            _emit,
            lambda: ComposeRagSearchClassified(
                conversation_id=conversation_id,
                provider=self.provider,
                classifier_model=classifier_model,
                requires_search=requires_search,
                document_count=document_count,
                documents_with_unreadable_structure=documents_with_unreadable_structure,
            ),
            self.actor_id,
            occurred_at,
        )
