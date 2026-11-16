from uuid import UUID

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user, get_current_user_id
from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.lib.permissions import can
from sparkth.lib.permissions.scopes import USER, build_scope_path
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.permissions import CONVERSATION_WRITE
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


logger = get_logger(__name__)


async def get_conversation_owner_id(conversation: Conversation = Depends(get_conversation)) -> int:
    """Return the id of the user who owns the conversation named in the path.

    Raises ConversationNotFound for an unknown UUID, before any permission is checked.
    """
    return conversation.user_id


async def get_turn_conversation(
    request: ChatCompletionRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
) -> Conversation:
    """Return the conversation a turn is checked at.

    A turn that names a conversation gets the stored one, whoever owns it. A first message gets an unsaved
    stand-in owned by the caller: only its path is checked, it is never stored, and the turn creates its
    own conversation.

    Takes the turn's body under the route's own parameter name and type, so the request still has one
    flat body. Raises ConversationNotFound when the named conversation does not exist, which the
    registry renders as a 404.
    """
    if request.conversation_id is not None:
        return await service.get_conversation(session, request.conversation_id)
    # Empty provider and model: the stand-in is never saved.
    return Conversation(user_id=user_id, provider="", model="")


async def get_attachable_document_ids(
    request: ChatCompletionRequest,
    turn_conversation: Conversation = Depends(get_turn_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[int]:
    """Return the document ids a turn may attach to its conversation.

    The ids the request names when the caller holds write access at the conversation owner's user scope,
    otherwise an empty list. Never refuses the turn.
    """
    if not request.document_ids:
        return []
    owner_scope_path = build_scope_path(USER, str(turn_conversation.user_id))
    if await can(current_user, CONVERSATION_WRITE, USER, owner_scope_path, session):
        return request.document_ids
    logger.warning(
        "Dropped %d document(s) from a turn: no write access at the scope of conversation owner %s",
        len(request.document_ids),
        turn_conversation.user_id,
    )
    return []
