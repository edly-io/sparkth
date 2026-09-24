import json
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.analytics import as_utc, emit_documents_detached
from sparkth.plugins.chat.exceptions import ConversationNotFound, DocumentNotFound
from sparkth.plugins.chat.messages import text_of
from sparkth.plugins.chat.models import Conversation, ConversationAttachment, Message, MessageType
from sparkth.plugins.chat.schemas import ChatMessage
from sparkth.plugins.chat.types import AttachOutcome, ConversationDocuments

logger = get_logger(__name__)


class ChatService:
    async def create_conversation(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        llm_config_id: int | None,
        provider: str,
        model: str,
        title: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            llm_config_id=llm_config_id,
            provider=provider,
            model=model,
            title=title,
        )

        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

        logger.info("Created conversation %s for user %s", conversation.id, user_id)
        return conversation

    async def get_or_create_conversation(
        self,
        session: AsyncSession,
        *,
        conversation_uuid: UUID | None,
        user_id: int,
        llm_config_id: int | None,
        provider: str,
        model: str,
        title: str | None = None,
    ) -> tuple[Conversation, bool]:
        """Resolve the conversation a request names, or start one when it names none.

        ``title`` is used only when starting one. Ownership is part of resolving: a uuid that
        belongs to another user is as absent as one that does not exist.

        Returns:
            The conversation, and whether this call started it. Callers that do first-turn work —
            scheduling title generation, say — read the flag rather than re-deriving the rule from
            the uuid, which would put the same decision in two places.

        Raises:
            ConversationNotFound: the uuid does not resolve to a conversation this user owns.
                Never resolved by starting a fresh one, which would strand the conversation the
                client meant to continue.
        """
        if conversation_uuid is None:
            conversation = await self.create_conversation(
                session,
                user_id=user_id,
                llm_config_id=llm_config_id,
                provider=provider,
                model=model,
                title=title,
            )
            return conversation, True

        existing = await self.require_owned_conversation(session, conversation_uuid, user_id)
        return existing, False

    async def get_conversation_by_uuid(self, session: AsyncSession, uuid: UUID, user_id: int) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.uuid == uuid,
            Conversation.user_id == user_id,
        )
        result = await session.exec(statement)
        return result.first()

    async def require_owned_conversation(
        self,
        session: AsyncSession,
        conversation_uuid: UUID,
        user_id: int,
    ) -> Conversation:
        """Return the caller's conversation.

        Raises:
            ConversationNotFound: no such conversation, or it belongs to someone else.
        """
        conversation = await self.get_conversation_by_uuid(session, conversation_uuid, user_id)
        if conversation is None:
            logger.warning("Conversation %s not found for user %s", conversation_uuid, user_id)
            raise ConversationNotFound(_("Conversation not found"))
        return conversation

    async def list_conversations(
        self, session: AsyncSession, user_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[list[Conversation], int]:
        count_statement = select(func.count(col(Conversation.id))).where(
            Conversation.user_id == user_id,
        )
        total = (await session.exec(count_statement)).one()

        statement = (
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
            )
            .order_by(col(Conversation.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        conversations = list(result.all())

        return conversations, total

    async def add_message(
        self,
        session: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
        tokens_used: int | None = None,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
        is_error: bool = False,
        message_type: MessageType = "text",
        attachment_name: str | None = None,
        attachment_size: int | None = None,
    ) -> Message:
        metadata_json = json.dumps(metadata) if metadata else None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            cost=cost,
            model_metadata=metadata_json,
            is_error=is_error,
            message_type=message_type,
            attachment_name=attachment_name,
            attachment_size=attachment_size,
        )

        session.add(message)

        if tokens_used or cost:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.exec(statement)
            conversation = result.first()

            if conversation:
                if tokens_used:
                    conversation.total_tokens_used += tokens_used
                if cost:
                    conversation.total_cost += cost
                session.add(conversation)

        await session.commit()
        await session.refresh(message)

        return message

    async def get_conversation_messages(
        self,
        session: AsyncSession,
        conversation_id: int,
        limit: int | None = None,
        offset: int | None = None,
        exclude_errors: bool = True,
    ) -> list[Message]:
        """
        Return conversation messages, optionally excluding error messages.
        """
        statement = (
            select(Message).where(Message.conversation_id == conversation_id).order_by(col(Message.created_at).asc())
        )

        if exclude_errors:
            statement = statement.where(Message.is_error == False)  # noqa: E712

        if limit is not None:
            statement = statement.limit(limit)

        if offset is not None:
            statement = statement.offset(offset)

        result = await session.exec(statement)
        return list(result.all())

    async def get_last_conversation_message(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> Message | None:
        """Return the most recently created message for a conversation, or None."""
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(col(Message.created_at).desc())
            .limit(1)
        )
        result = await session.exec(statement)
        return result.first()

    async def update_conversation_title(
        self,
        session: AsyncSession,
        conversation_id: int,
        user_id: int,
        title: str,
    ) -> None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await session.exec(statement)
        conversation = result.first()
        if conversation:
            conversation.title = title
            session.add(conversation)
            await session.commit()
        else:
            logger.warning("Conversation %s not found for title update", conversation_id)

    async def attach_document(
        self,
        session: AsyncSession,
        conversation_id: int,
        document_id: int,
    ) -> tuple[ConversationAttachment, bool]:
        """Attach a document to a conversation (upsert-safe).

        Returns:
            The attachment, and whether this call created it. A caller that records
            attaching as an action needs the flag: this method is upsert-safe, so a
            repeat returns the existing row and nothing happened.
        """
        # Check if already exists
        stmt = select(ConversationAttachment).where(
            ConversationAttachment.conversation_id == conversation_id,
            ConversationAttachment.document_id == document_id,
        )
        result = await session.exec(stmt)
        existing = result.first()
        if existing is not None:
            logger.info(
                "Document %s already attached to conversation %s",
                document_id,
                conversation_id,
            )
            return existing, False

        # Try to insert new
        attachment = ConversationAttachment(
            conversation_id=conversation_id,
            document_id=document_id,
        )
        session.add(attachment)
        try:
            await session.flush()
            await session.commit()
            await session.refresh(attachment)
            logger.info(
                "Document %s attached to conversation %s",
                document_id,
                conversation_id,
            )
            return attachment, True
        except IntegrityError:
            # Race condition — another process inserted between our check and insert
            await session.rollback()
            # Query again to get the existing row
            result = await session.exec(stmt)
            existing = result.first()
            if existing is None:
                logger.error(
                    "IntegrityError but row not found after rollback for conversation_id=%s, document_id=%s",
                    conversation_id,
                    document_id,
                )
                raise
            # Another request won the race, so this call did not create it.
            return existing, False

    async def detach_document(
        self,
        session: AsyncSession,
        conversation_id: int,
        document_id: int,
    ) -> datetime | None:
        """Detach a document from a conversation.

        Returns:
            When the removed attachment was attached, or ``None`` if there was nothing to
            remove. The row is gone afterwards, so a caller that wants to know how long
            the document had been in play can only learn it here.
        """
        stmt = select(ConversationAttachment).where(
            ConversationAttachment.conversation_id == conversation_id,
            ConversationAttachment.document_id == document_id,
        )
        result = await session.exec(stmt)
        attachment = result.first()
        if attachment is None:
            return None
        attached_at = attachment.attached_at
        await session.delete(attachment)
        await session.commit()
        logger.info(
            "Document %s detached from conversation %s",
            document_id,
            conversation_id,
        )
        return attached_at

    async def require_owned_document(
        self,
        session: AsyncSession,
        document_id: int,
        user_id: int,
    ) -> Document:
        """Return the caller's document.

        Raises:
            DocumentNotFound: no such document, it is deleted, or it belongs to someone else.
        """
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
            Document.is_deleted == False,  # noqa: E712
        )
        result = await session.exec(stmt)
        document = result.first()
        if document is None:
            logger.warning("Document %s not found for user %s", document_id, user_id)
            raise DocumentNotFound(_("Document not found or not accessible"))
        return document

    async def attach_owned_documents(
        self,
        session: AsyncSession,
        conversation_id: int,
        document_ids: list[int],
        user_id: int,
    ) -> AttachOutcome:
        """Attach the documents the user owns, skipping and logging the ids they do not.

        A request names ids, so it can name one belonging to someone else. Skipping keeps the
        rest of a legitimate request working; a bulk lookup keeps it to one query.

        Returns:
            What actually happened: the attachments this call created, and how many distinct
            ids were asked for against how many were dropped. Both counts are over distinct ids,
            so a repeated id cannot make the two disagree. The instructor is told none of
            this, so the caller is the only place it can be recorded.
        """
        owned_result = await session.exec(
            select(Document.id).where(
                col(Document.id).in_(document_ids),
                Document.user_id == user_id,
                Document.is_deleted == False,  # noqa: E712
            )
        )
        owned_ids = {document_id for document_id in owned_result.all() if document_id is not None}
        requested = set(document_ids)
        skipped = requested - owned_ids
        if skipped:
            logger.warning("Skipped %d unowned/deleted document IDs for user %s: %s", len(skipped), user_id, skipped)
        created: list[ConversationAttachment] = []
        for document_id in owned_ids:
            attachment, was_created = await self.attach_document(session, conversation_id, document_id)
            if was_created:
                created.append(attachment)
        return AttachOutcome(
            created=created,
            requested_count=len(requested),
            skipped_count=len(skipped),
        )

    async def add_incoming_messages(
        self,
        session: AsyncSession,
        conversation_id: int,
        messages: list[ChatMessage],
    ) -> list[Message]:
        """Store the turns a request carries, so reopening the conversation shows them.

        Returns the stored rows. This is the only place a request's content blocks are
        flattened into message text, so a caller that needs to measure what was stored —
        analytics does — reads it from here rather than re-deriving it from the request
        and drifting from this flattening.
        """
        stored: list[Message] = []
        for message in messages:
            stored.append(
                await self.add_message(
                    session=session,
                    conversation_id=conversation_id,
                    role=message.role,
                    # A turn of attachments alone still needs a body, or the transcript shows a blank.
                    content=text_of(message) or "[Document attachment]",
                    message_type="attachment" if message.attachment else "text",
                    attachment_name=message.attachment.name if message.attachment else None,
                    attachment_size=message.attachment.size if message.attachment else None,
                )
            )
        return stored

    async def record_error_message(
        self,
        session: AsyncSession,
        conversation_uuid: UUID | None,
        user_id: int,
        message: str,
    ) -> None:
        """Store an assistant error against an existing conversation, so a reload still shows it.

        Does nothing without a conversation: the failure can predate one, and creating a
        conversation to hold an error would leave the user a thread containing only that error.
        A database failure here is swallowed — an error is already on its way to the user, and
        raising would replace it with a less useful one.
        """
        if conversation_uuid is None:
            return
        try:
            conversation = await self.get_conversation_by_uuid(session, conversation_uuid, user_id)
            if conversation and conversation.id is not None:
                await self.add_message(
                    session=session,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=message,
                    is_error=True,
                )
        except SQLAlchemyError:
            logger.exception("Failed to record error message for conversation %s", conversation_uuid)

    async def list_conversation_attachments(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> ConversationDocuments:
        """List the documents attached to a conversation, split by whether chat can use them.

        Chat can only work from READY documents, but the ones it cannot use are the more
        interesting half: an instructor whose document is still ingesting gets a reply that
        ignores it, with nothing to say why. Filtering them out inside the query threw that
        away before any caller could see it, so the split is returned instead of applied.
        """
        stmt = (
            select(Document)
            .join(
                ConversationAttachment,
                ConversationAttachment.document_id == Document.id,  # type: ignore[arg-type]
            )
            .where(ConversationAttachment.conversation_id == conversation_id)
        )
        result = await session.exec(stmt)
        ready: list[Document] = []
        unusable: list[Document] = []
        for document in result.all():
            if document.status == DocumentStatus.READY and not document.is_deleted:
                ready.append(document)
            else:
                unusable.append(document)
        return ConversationDocuments(ready=ready, unusable=unusable)


async def detach_deleted_document(session: AsyncSession, document: Document) -> None:
    """Clear a deleted document out of every conversation that had it attached."""
    stmt = (
        select(ConversationAttachment, Conversation.uuid)
        .join(Conversation, col(ConversationAttachment.conversation_id) == col(Conversation.id))
        .where(ConversationAttachment.document_id == document.id)
    )
    rows = (await session.exec(stmt)).all()
    if not rows:
        return

    removed_at = datetime.now(timezone.utc)
    detachments = [
        (str(conversation_uuid), max(int((removed_at - as_utc(attachment.attached_at)).total_seconds()), 0))
        for attachment, conversation_uuid in rows
    ]
    for attachment, _uuid in rows:
        await session.delete(attachment)
    await session.flush()

    logger.info("Document %s detached from %s conversation(s) on deletion", document.id, len(rows))
    await emit_documents_detached(
        detachments,
        document_id=cast(int, document.id),
        actor_id=str(document.user_id),
        occurred_at=removed_at,
    )


def get_chat_service() -> ChatService:
    """Dependency to get chat service."""
    return ChatService()
