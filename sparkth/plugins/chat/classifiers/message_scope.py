"""The message-scope classifier: is this chat turn about designing a course?

A negative verdict ends the turn — the chat model is never reached and the user gets the
refusal sentence — so this module fails open and logs every refusal it decides.
"""

from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from sparkth.lib.log import get_logger
from sparkth.plugins.chat.analytics import ChatClassifierAnalytics, ScopeVerdict
from sparkth.plugins.chat.classifiers.base import BaseClassifier
from sparkth.plugins.chat.constants import (
    MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY,
    MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
)
from sparkth.plugins.chat.exceptions import ClassifierError
from sparkth.plugins.chat.schemas import HistoryTurn, MessageScopeInput, MessageScopeVerdict

logger = get_logger(__name__)


class MessageScopeClassifier(BaseClassifier[MessageScopeInput, MessageScopeVerdict]):
    """Decides whether a chat turn falls within the assistant's learning-design scope."""

    def __init__(
        self,
        provider_name: str,
        api_key: str,
        user_id: int,
        analytics: ChatClassifierAnalytics | None = None,
    ) -> None:
        """``user_id`` never reaches the model; it is logged, and is all a refusal on a first
        message can be traced by. ``analytics`` is optional: without it a decision is simply
        not measured.
        """
        super().__init__(
            MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
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

        current_turn = payload.query
        if payload.attached_document_names:
            document_list = ", ".join(f'"{name}"' for name in payload.attached_document_names)
            current_turn = (
                f"[The user has attached the following documents to this conversation: {document_list}]"
                f"\n\n{payload.query}"
            )
        messages.append(HumanMessage(content=current_turn))
        return messages

    async def in_scope(
        self,
        query: str,
        history: list[HistoryTurn] | None = None,
        attached_document_names: list[str] | None = None,
        conversation_uuid: UUID | None = None,
    ) -> bool:
        """Return whether this turn is in scope, as the single boolean callers act on.

        Judging scope is all this does. A turn is expected to carry something the user sent —
        text, attachments, or both — and the request boundary rejects one that carries neither,
        so nothing here compensates for a turn that is missing. ``query`` may legitimately be
        empty when documents are attached: sending a document with no words is how a user asks
        the assistant to read it, and the attachment names are what the model judges instead.

        ``conversation_uuid`` never reaches the model. It is logged on a refusal so the
        decision can be traced to the thread a user reports, and is ``None`` on the first
        message of a new chat, which is judged before any conversation row exists.

        Fails open: a failed classification is treated as in scope, leaving the chat model's
        own system prompt to refuse if it must. A refusal ends the turn, so it is never
        inferred from an error.
        """
        payload = MessageScopeInput(
            query=query,
            history=history or [],
            attached_document_names=attached_document_names or [],
        )
        try:
            verdict = await self.classify(payload)
        except ClassifierError as exc:
            logger.warning(
                "Message scope classifier failed, defaulting to in_scope=True: user_id=%s conversation_uuid=%s: %s",
                self._user_id,
                conversation_uuid,
                exc,
            )
            # Recorded, not silent: the rate of turns admitted unjudged is invisible otherwise.
            self._record(ScopeVerdict.NOT_JUDGED, conversation_uuid, history, attached_document_names, query)
            return True

        if not verdict.in_scope:
            # The only record of a refusal: the chat model is never reached. Counts and lengths
            # only, since the message may hold course content.
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
        self._record(
            ScopeVerdict.IN_SCOPE if verdict.in_scope else ScopeVerdict.OUT_OF_SCOPE,
            conversation_uuid,
            history,
            attached_document_names,
            query,
        )
        return verdict.in_scope

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
