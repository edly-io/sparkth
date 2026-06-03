from functools import lru_cache
from typing import cast
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.service import ChatService
from app.models.user import User


@lru_cache
def get_chat_system_config() -> ChatSystemConfig:
    """Dependency to get chat system configuration from environment variables."""
    return ChatSystemConfig()


def get_chat_service() -> ChatService:
    """Dependency to get chat service."""
    return ChatService()


async def get_owned_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> Conversation:
    """Resolve a conversation UUID to its model, 404-ing if absent or not owned."""
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=cast(int, current_user.id),
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation
