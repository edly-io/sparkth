from typing import cast
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.models.user import User
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.service import ChatService, get_chat_service


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
