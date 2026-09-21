from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
from sparkth.plugins.chat.analytics import ChatAttachmentAnalytics
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.routes.dependencies import get_owned_conversation
from sparkth.plugins.chat.schemas import (
    AttachedDocumentResponse,
    ConversationAttachmentCreate,
    ConversationAttachmentResponse,
)
from sparkth.plugins.chat.service import ChatService, get_chat_service

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[AttachedDocumentResponse],
)
async def list_conversation_attachments(
    conversation: Conversation = Depends(get_owned_conversation),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> list[AttachedDocumentResponse]:
    attachments = await service.list_conversation_attachments(
        session,
        conversation_id=cast(int, conversation.id),
    )
    # Only the usable half is listed, which is what this endpoint has always returned.
    return [
        AttachedDocumentResponse(
            id=cast(int, document.id),
            name=document.name,
            size=None,
        )
        for document in attachments.ready
    ]


@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationAttachmentResponse,
)
async def attach_document_to_conversation(
    body: ConversationAttachmentCreate,
    background_tasks: BackgroundTasks,
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationAttachmentResponse:
    document = await service.require_owned_document(session, body.document_id, cast(int, current_user.id))
    attachment, was_created = await service.attach_document(
        session,
        conversation_id=cast(int, conversation.id),
        document_id=cast(int, document.id),
    )
    if was_created:
        # Attaching is upsert-safe, so a repeat returns the existing row and is not an
        # action. Timed by that row, which is the only record of when it happened.
        _analytics(background_tasks, conversation, current_user).schedule_document_attached(
            document_id=cast(int, document.id),
            source="explicit",
            occurred_at=attachment.attached_at,
        )
    return ConversationAttachmentResponse(
        id=cast(int, attachment.id),
        conversation_id=attachment.conversation_id,
        document_id=attachment.document_id,
        attached_at=attachment.attached_at,
    )


@router.delete(
    "/conversations/{conversation_id}/attachments/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_document_from_conversation(
    document_id: int,
    background_tasks: BackgroundTasks,
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    await service.require_owned_document(session, document_id, cast(int, current_user.id))
    attached_at = await service.detach_document(
        session,
        conversation_id=cast(int, conversation.id),
        document_id=document_id,
    )
    if attached_at is not None:
        # The row is gone, so there is nothing left recording when this happened: the
        # removal is stamped here, and how long the document had been in play is measured
        # from the attachment that no longer exists.
        removed_at = datetime.now(timezone.utc)
        _analytics(background_tasks, conversation, current_user).schedule_document_detached(
            document_id=document_id,
            seconds_attached=max(int((removed_at - _as_utc(attached_at)).total_seconds()), 0),
            occurred_at=removed_at,
        )


def _as_utc(value: datetime) -> datetime:
    """Read a stored timestamp as UTC-aware; SQLite returns the column naive."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _analytics(
    background_tasks: BackgroundTasks, conversation: Conversation, current_user: User
) -> ChatAttachmentAnalytics:
    """The attachment events' scheduling seam for this request."""
    return ChatAttachmentAnalytics(
        background_tasks=background_tasks,
        conversation_id=str(conversation.uuid),
        actor_id=str(cast(int, current_user.id)),
    )
