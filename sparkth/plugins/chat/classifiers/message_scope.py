"""The message-scope classifier: which registered chat job is this turn for?

A turn that fits no job ends with the refusal sentence and never reaches the chat model. So this
module fails open, answering with the caller's fallback job when the classification fails or
names no offered job, and it logs every refusal it decides.
"""

from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.analytics import ChatClassifierAnalytics, ScopeVerdict
from sparkth.plugins.chat.classifiers.base import BaseClassifier
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY,
    NO_RESPONSIBILITY,
)
from sparkth.plugins.chat.exceptions import ClassifierError
from sparkth.plugins.chat.prompt import render_scope_classifier_prompt
from sparkth.plugins.chat.schemas import HistoryTurn, MessageScopeInput, MessageScopeVerdict, scope_verdict_model

logger = get_logger(__name__)


class MessageScopeClassifier(BaseClassifier[MessageScopeInput, MessageScopeVerdict]):
    """Decides which registered chat job a turn belongs to, or that it belongs to none."""

    def __init__(
        self,
        jobs: dict[str, ChatResponsibility],
        provider_name: str,
        api_key: str,
        user_id: int,
        analytics: ChatClassifierAnalytics | None = None,
    ) -> None:
        """``jobs`` is this request's enabled jobs by name, from ``enabled_responsibilities``. The
        prompt lists them, and the answer schema accepts only their names or ``NO_RESPONSIBILITY``. ``user_id`` never
        reaches the model; it is logged, and is all a refusal on a first message can be traced
        by. ``analytics`` is optional: without it a decision is simply not measured.
        """
        super().__init__(
            render_scope_classifier_prompt(jobs),
            scope_verdict_model(jobs),
            provider_name,
            api_key,
        )
        self._user_id = user_id
        self._analytics = analytics

    def _build_messages(self, payload: MessageScopeInput) -> list[BaseMessage]:
        """Replay the recent conversation as real turns, then the current message.

        The prompt judges the job from the conversation rather than the latest message alone —
        "yes, for nurses" belongs to a job only as a reply to a question the assistant asked — so
        history is replayed as alternating turns instead of being summarised. Roles the model
        has no turn type for (``tool``, ``system``) are dropped: they are not what the user
        asked. Attachment names ride on the current turn, because a message about "these
        documents" can only be judged if the classifier knows documents are in play. So does
        the job the conversation is already doing, which settles a message that fits several jobs.
        """
        messages: list[BaseMessage] = []
        for turn in payload.history[-MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY:]:
            match turn["role"]:
                case "user":
                    messages.append(HumanMessage(content=turn["content"]))
                case "assistant":
                    messages.append(AIMessage(content=turn["content"]))

        notes: list[str] = []
        if payload.current_job:
            notes.append(f'[This conversation has been doing the job "{payload.current_job}"]')
        if payload.attached_document_names:
            document_list = ", ".join(f'"{name}"' for name in payload.attached_document_names)
            notes.append(f"[The user has attached the following documents to this conversation: {document_list}]")
        current_turn = "\n".join(notes) + f"\n\n{payload.query}" if notes else payload.query
        messages.append(HumanMessage(content=current_turn))
        return messages

    async def responsibility_for(
        self,
        query: str,
        history: list[HistoryTurn] | None = None,
        attached_document_names: list[str] | None = None,
        conversation_uuid: UUID | None = None,
        fallback: str = DEFAULT_RESPONSIBILITY,
    ) -> str | None:
        """Return the name of the offered job this turn belongs to, or ``None`` for none.

        ``query`` may be empty when documents are attached; the attachment names are judged
        instead. ``conversation_uuid`` never reaches the model. It is logged so a decision can
        be traced, and it is ``None`` on a new chat's first message. On a later turn ``fallback``
        is the stored job, which is also shown to the model as the job the conversation is doing.

        Fails open to ``fallback``: the default job on a first message, the stored job on a
        later turn. That covers a failed classification, including an answer that is not an
        offered job and so fails the schema, because a refusal ends the turn and is never inferred
        from an error.
        """
        payload = MessageScopeInput(
            query=query,
            history=history or [],
            attached_document_names=attached_document_names or [],
            current_job=fallback if conversation_uuid else None,
        )
        try:
            verdict = await self.classify(payload)
        except ClassifierError as exc:
            logger.warning(
                "Message scope classifier failed, defaulting to responsibility=%s: user_id=%s conversation_uuid=%s: %s",
                fallback,
                self._user_id,
                conversation_uuid,
                exc,
            )
            # Recorded, not silent: the rate of turns admitted unjudged is invisible otherwise.
            self._record(ScopeVerdict.NOT_JUDGED, conversation_uuid, history, attached_document_names, query)
            return fallback

        job = None if verdict.responsibility == NO_RESPONSIBILITY else verdict.responsibility
        if job is None:
            self._log_refusal(verdict, conversation_uuid, history, attached_document_names, query)
        self._record(
            ScopeVerdict.OUT_OF_SCOPE if job is None else ScopeVerdict.IN_SCOPE,
            conversation_uuid,
            history,
            attached_document_names,
            query,
        )
        return job

    def _log_refusal(
        self,
        verdict: MessageScopeVerdict,
        conversation_uuid: UUID | None,
        history: list[HistoryTurn] | None,
        attached_document_names: list[str] | None,
        query: str,
    ) -> None:
        """Log a refusal, the only record of it since the chat model is never reached.

        Counts and lengths only, because the message may hold course content.
        """
        logger.warning(
            "Scope classifier refused a message: user_id=%s conversation_uuid=%s model=%s "
            "reason=%r history_turns=%d attachments=%d query_len=%d",
            self._user_id,
            conversation_uuid,
            self.model,
            verdict.refusal_reason,
            len(history or []),
            len(attached_document_names or []),
            len(query),
        )

    def _record(
        self,
        verdict: ScopeVerdict,
        conversation_uuid: UUID | None,
        history: list[HistoryTurn] | None,
        attached_document_names: list[str] | None,
        query: str,
    ) -> None:
        """Queue the decision, measuring the message rather than carrying it.

        ``refusal_reason`` is omitted: it can quote course content, so it stays in the log.
        """
        if self._analytics is None:
            return
        self._analytics.schedule_scope_classified(
            conversation_id=str(conversation_uuid) if conversation_uuid else None,
            classifier_model=self.model,
            verdict=verdict,
            history_turns=len(history or []),
            attachment_count=len(attached_document_names or []),
            query_length=len(query),
            # Records the moment the decision is made, not when the classification started.
            occurred_at=datetime.now(timezone.utc),
        )
