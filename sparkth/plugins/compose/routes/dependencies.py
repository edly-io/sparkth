from typing import cast
from uuid import UUID

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.service import ComposeService, get_compose_service


async def get_owned_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
) -> Conversation:
    """Resolve a conversation UUID to its model.

    Raises ConversationNotFound when it is absent or not the caller's, which the registry renders
    as a 404.
    """
    return await service.require_owned_conversation(session, conversation_id, cast(int, current_user.id))
