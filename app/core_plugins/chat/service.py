import json
from typing import Any
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.chat.models import Conversation, Message, MessageType

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
        active_drive_file_id: int | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            llm_config_id=llm_config_id,
            provider=provider,
            model=model,
            title=title,
            system_prompt=system_prompt,
            active_drive_file_id=active_drive_file_id,
        )

        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} for user {user_id}")
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

    async def set_active_drive_file(
        self,
        session: AsyncSession,
        conversation_id: int,
        user_id: int,
        drive_file_id: int | None,
    ) -> None:
        """Set or clear the active drive file for a conversation."""
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        result = await session.exec(stmt)
        conversation = result.first()
        if conversation:
            conversation.active_drive_file_id = drive_file_id
            session.add(conversation)
            await session.commit()

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
            logger.warning(f"Conversation {conversation_id} not found for title update")
