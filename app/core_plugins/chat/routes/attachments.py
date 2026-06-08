from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.routes.dependencies import get_owned_conversation
from app.core_plugins.chat.schemas import (
    AttachedDriveFileResponse,
    ConversationAttachmentCreate,
    ConversationAttachmentResponse,
)
from app.core_plugins.chat.service import ChatService, get_chat_service
from app.lib.db import get_async_session
from app.models.user import User

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[AttachedDriveFileResponse],
)
async def list_conversation_attachments(
    conversation: Conversation = Depends(get_owned_conversation),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> list[AttachedDriveFileResponse]:
    drive_files = await service.list_conversation_attachments(
        session,
        conversation_id=cast(int, conversation.id),
    )
    return [AttachedDriveFileResponse(id=cast(int, f.id), name=f.name, size=f.size) for f in drive_files]


@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationAttachmentResponse,
)
async def attach_file_to_conversation(
    body: ConversationAttachmentCreate,
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationAttachmentResponse:
    drive_file = await service.get_user_owned_drive_file(
        session,
        drive_file_id=body.drive_file_id,
        user_id=cast(int, current_user.id),
    )
    if not drive_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drive file not found or not accessible",
        )
    attachment = await service.attach_drive_file(
        session,
        conversation_id=cast(int, conversation.id),
        drive_file_id=cast(int, drive_file.id),
    )
    return ConversationAttachmentResponse(
        id=cast(int, attachment.id),
        conversation_id=attachment.conversation_id,
        drive_file_id=attachment.drive_file_id,
        attached_at=attachment.attached_at,
    )


@router.delete(
    "/conversations/{conversation_id}/attachments/{drive_file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_file_from_conversation(
    drive_file_id: int,
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    drive_file = await service.get_user_owned_drive_file(
        session,
        drive_file_id=drive_file_id,
        user_id=cast(int, current_user.id),
    )
    if not drive_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drive file not found or not accessible",
        )
    await service.detach_drive_file(
        session,
        conversation_id=cast(int, conversation.id),
        drive_file_id=drive_file_id,
    )
