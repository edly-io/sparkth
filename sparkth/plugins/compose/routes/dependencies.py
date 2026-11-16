from typing import cast
from uuid import UUID

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
from sparkth.lib.permissions.scopes import USER, build_scope_path
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.schemas import ChatCompletionRequest
from sparkth.plugins.compose.service import ComposeService, get_compose_service


async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
) -> Conversation:
    """Resolve a conversation UUID to its model, whoever owns it.

    Raises ConversationNotFound when no conversation has that UUID, which the registry renders as
    a 404.
    """
    return await service.get_conversation(session, conversation_id)


async def get_turn_conversation(
    request: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
) -> Conversation:
    """Return the conversation a turn is checked at.

    A turn that names a conversation gets the stored one, whoever owns it. A first message gets an unsaved
    conversation owned by the caller, under the caller's own user scope, which the turn will go on to create.

    Takes the turn's body under the route's own parameter name and type, so the request still has one
    flat body. Raises ConversationNotFound when the named conversation does not exist, which the
    registry renders as a 404.
    """
    if request.conversation_id is not None:
        return await service.get_conversation(session, request.conversation_id)
    # Never saved, so provider and model stay empty; the parent path is set here as nothing else fills it.
    return Conversation(
        user_id=cast(int, current_user.id),
        provider="",
        model="",
        parent_scope_path=build_scope_path(USER, str(current_user.id)),
    )
