import json
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.chat.models import Conversation, ConversationAttachment, Message, MessageType
from app.models.drive import DriveFile
from app.rag.types import RagStatus

logger = get_logger(__name__)


class ChatService:
    async def create_conversation(
        self,
        session: AsyncSession,
        user_id: int,
        llm_config_id: int | None,
        provider: str,
        model: str,
        title: str | None = None,
        system_prompt: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            llm_config_id=llm_config_id,
            provider=provider,
            model=model,
            title=title,
            system_prompt=system_prompt,
        )

        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

        logger.info("Created conversation %s for user %s", conversation.id, user_id)
        return conversation

    async def get_conversation_by_uuid(self, session: AsyncSession, uuid: UUID, user_id: int) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.uuid == uuid,
            Conversation.user_id == user_id,
        )
        result = await session.exec(statement)
        return result.first()

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

    async def attach_drive_file(
        self,
        session: AsyncSession,
        conversation_id: int,
        drive_file_id: int,
    ) -> ConversationAttachment:
        """Attach a drive file to a conversation (upsert-safe)."""
        # Check if already exists
        stmt = select(ConversationAttachment).where(
            ConversationAttachment.conversation_id == conversation_id,
            ConversationAttachment.drive_file_id == drive_file_id,
        )
        result = await session.exec(stmt)
        existing = result.first()
        if existing is not None:
            logger.info(
                "Drive file %s already attached to conversation %s",
                drive_file_id,
                conversation_id,
            )
            return existing

        # Try to insert new
        attachment = ConversationAttachment(
            conversation_id=conversation_id,
            drive_file_id=drive_file_id,
        )
        session.add(attachment)
        try:
            await session.flush()
            await session.commit()
            await session.refresh(attachment)
            logger.info(
                "Drive file %s attached to conversation %s",
                drive_file_id,
                conversation_id,
            )
            return attachment
        except IntegrityError:
            # Race condition — another process inserted between our check and insert
            await session.rollback()
            # Query again to get the existing row
            result = await session.exec(stmt)
            existing = result.first()
            if existing is None:
                logger.error(
                    "IntegrityError but row not found after rollback for conversation_id=%s, drive_file_id=%s",
                    conversation_id,
                    drive_file_id,
                )
                raise
            return existing

    async def detach_drive_file(
        self,
        session: AsyncSession,
        conversation_id: int,
        drive_file_id: int,
    ) -> None:
        """Detach a drive file from a conversation."""
        stmt = select(ConversationAttachment).where(
            ConversationAttachment.conversation_id == conversation_id,
            ConversationAttachment.drive_file_id == drive_file_id,
        )
        result = await session.exec(stmt)
        attachment = result.first()
        if attachment:
            await session.delete(attachment)
            await session.commit()
            logger.info(
                "Drive file %s detached from conversation %s",
                drive_file_id,
                conversation_id,
            )

    async def list_conversation_attachments(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> list[DriveFile]:
        """List ready drive files attached to a conversation."""
        stmt = (
            select(DriveFile)
            .join(
                ConversationAttachment,
                ConversationAttachment.drive_file_id == DriveFile.id,  # type: ignore
            )
            .where(
                ConversationAttachment.conversation_id == conversation_id,
                DriveFile.rag_status == RagStatus.READY,
                DriveFile.is_deleted == False,  # noqa: E712
            )
        )
        result = await session.exec(stmt)
        return list(result.all())
