"""The message-scope classifier: does this turn belong to any of the assistant's capabilities?

A turn that fits none ends with the refusal sentence and never reaches the chat model. A failed
classification is raised to the caller, which fails the turn, so no turn reaches the chat model
without a verdict. It logs every refusal it decides.
"""

from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from sparkth.lib.chat.hooks import ChatCapability
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.analytics import ChatClassifierAnalytics, ScopeVerdict
from sparkth.plugins.chat.classifiers.base import BaseClassifier
from sparkth.plugins.chat.constants import MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY, SCOPE_CHECK_ERRORS
from sparkth.plugins.chat.exceptions import ScopeCheckError
from sparkth.plugins.chat.prompt import render_scope_classifier_prompt
from sparkth.plugins.chat.schemas import HistoryTurn, MessageScopeInput, MessageScopeVerdict

logger = get_logger(__name__)


class MessageScopeClassifier(BaseClassifier[MessageScopeInput, MessageScopeVerdict]):
    """Decides whether a turn belongs to any of the assistant's capabilities."""

    def __init__(
        self,
        capabilities: list[ChatCapability],
        provider_name: str,
        api_key: str,
        user_id: int,
        analytics: ChatClassifierAnalytics | None = None,
    ) -> None:
        """``capabilities`` are this request's enabled capabilities; the prompt lists each by its
        title and scope. ``user_id`` never reaches the model; it is logged, and is all a refusal
        on a first message can be traced by. ``analytics`` is optional: without it a decision is
        simply not measured.
        """
        super().__init__(
            render_scope_classifier_prompt(capabilities),
            MessageScopeVerdict,
            provider_name,
            api_key,
        )
        self._user_id = user_id
        self._analytics = analytics

    def _build_messages(self, payload: MessageScopeInput) -> list[BaseMessage]:
        """Replay the recent conversation as real turns, then the current message.

        The prompt judges scope from the conversation rather than the latest message alone —
        "yes, for nurses" is in scope only as a reply to a question the assistant asked — so
        history is replayed as alternating turns instead of being summarised. Roles the model
        has no turn type for (``tool``, ``system``) are dropped: they are not what the user
        asked. Attachment names ride on the current turn, because a message about "these
        documents" can only be judged if the classifier knows documents are in play.
        """
        messages: list[BaseMessage] = []
        for turn in payload.history[-MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY:]:
            match turn["role"]:
                case "user":
                    messages.append(HumanMessage(content=turn["content"]))
                case "assistant":
                    messages.append(AIMessage(content=turn["content"]))

        notes: list[str] = []
        if payload.attached_document_names:
            document_list = ", ".join(f'"{name}"' for name in payload.attached_document_names)
            notes.append(f"[The user has attached the following documents to this conversation: {document_list}]")
        current_turn = "\n".join(notes) + f"\n\n{payload.query}" if notes else payload.query
        messages.append(HumanMessage(content=current_turn))
        return messages

    async def in_scope(
        self,
        query: str,
        history: list[HistoryTurn] | None = None,
        attached_document_names: list[str] | None = None,
        conversation_uuid: UUID | None = None,
    ) -> bool:
        """Return whether this turn belongs to any of the assistant's capabilities.

        ``query`` may be empty when documents are attached; the attachment names are judged
        instead. ``conversation_uuid`` never reaches the model. It is logged so a decision can
        be traced, and it is ``None`` on a new chat's first message.

        A turn is never admitted or refused without a verdict, so a failed classification is
        left to the caller and nothing is recorded for it here.

        Raises:
            ScopeCheckError: no verdict. Its ``cause`` is the classifier error, the OpenAI
                refusal, or the provider error underneath.
        """
        payload = MessageScopeInput(
            query=query,
            history=history or [],
            attached_document_names=attached_document_names or [],
        )
        try:
            verdict = await self.classify(payload)
        except SCOPE_CHECK_ERRORS as exc:
            raise ScopeCheckError(exc) from exc

        if not verdict.in_scope:
            self._log_refusal(verdict, conversation_uuid, history, attached_document_names, query)
        self._record(
            ScopeVerdict.IN_SCOPE if verdict.in_scope else ScopeVerdict.OUT_OF_SCOPE,
            conversation_uuid,
            history,
            attached_document_names,
            query,
        )
        return verdict.in_scope

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
