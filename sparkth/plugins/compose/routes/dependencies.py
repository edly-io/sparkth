from uuid import UUID

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
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


async def get_conversation_owner_id(conversation: Conversation = Depends(get_conversation)) -> str:
    """Return the id of the user who owns the conversation, as the object id of its ``user`` scope."""
    return str(conversation.user_id)


async def get_turn_owner_id(
    request: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
) -> str:
    """Return the ``user`` scope object id a turn is checked at: the caller's for a first message, which
    starts a conversation they will own, otherwise the owner of the conversation the turn names.

    Takes the turn's body under the route's own parameter name and type, so the request still has one
    flat body. Raises ConversationNotFound when the named conversation does not exist, which the
    registry renders as a 404.
    """
    if request.conversation_id is None:
        return str(current_user.id)
    conversation = await service.get_conversation(session, request.conversation_id)
    return str(conversation.user_id)
