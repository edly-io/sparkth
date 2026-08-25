"""The message-scope classifier: is this chat turn about designing a course?

A negative verdict ends the turn — the chat model is never reached and the user gets the
refusal sentence — so this module fails open and logs every refusal it decides.
"""

from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from sparkth.lib.log import get_logger
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

    def __init__(self, provider_name: str, api_key: str) -> None:
        super().__init__(
            MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
            MessageScopeInput,
            MessageScopeVerdict,
            provider_name,
            api_key,
        )

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

        A turn that says nothing and attaches nothing is out of scope, decided without a
        model call: there is no request to judge. An empty ``query`` *with* attachments is a
        real request — sending a document with no words is how a user asks the assistant to
        read it — so it goes to the model, which is told the attachment names.

        ``conversation_uuid`` never reaches the model. It is logged on a refusal so the
        decision can be traced to the thread a user reports, and is ``None`` on the first
        message of a new chat, which is judged before any conversation row exists.

        Fails open: a failed classification is treated as in scope, leaving the chat model's
        own system prompt to refuse if it must. A refusal ends the turn, so it is never
        inferred from an error.
        """
        if not query.strip() and not attached_document_names:
            logger.warning(
                "Refused a turn that said nothing and attached nothing, without a model call (conversation_uuid=%s)",
                conversation_uuid,
            )
            return False

        payload: dict[str, object] = {
            "query": query,
            "history": history or [],
            "attached_document_names": attached_document_names or [],
        }
        try:
            verdict = await self.classify(payload)
        except ClassifierError as exc:
            logger.warning("Message scope classifier failed, defaulting to in_scope=True: %s", exc)
            return True

        if not verdict.in_scope:
            # A refusal ends the turn before the chat model sees it, so this is the only
            # record of the judgement. The reason is the model's own, kept to a category by the
            # prompt and the field description because this log has never carried message text.
            # The history count shows how much context was available
            # versus the last MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY turns the model
            # actually got. Counts and lengths
            # only — the message itself may hold course content.
            logger.warning(
                "Scope classifier refused a message: conversation_uuid=%s model=%s reason=%r "
                "history_turns=%d attachments=%d query_len=%d",
                conversation_uuid,
                self.model,
                verdict.refusal_reason,
                len(history or []),
                len(attached_document_names or []),
                len(query),
            )
        return verdict.in_scope
