from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.core_plugins.chat.routes.dependencies import get_chat_service
from app.core_plugins.chat.schemas import (
    AttachedDriveFileResponse,
    ConversationAttachmentCreate,
    ConversationAttachmentResponse,
)
from app.core_plugins.chat.service import ChatService
from app.models.drive import DriveFile as DriveFileModel
from app.models.user import User

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/attachments",
    response_model=list[AttachedDriveFileResponse],
)
async def list_conversation_attachments(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> list[AttachedDriveFileResponse]:
    """List READY drive files attached to a conversation."""
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=current_user.id,  # type: ignore
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    drive_files = await service.list_conversation_attachments(
        session,
        conversation_id=conversation.id,  # type: ignore
    )
    return [
        AttachedDriveFileResponse(id=f.id, name=f.name, size=f.size)  # type: ignore
        for f in drive_files
    ]


@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationAttachmentResponse,
)
async def attach_file_to_conversation(
    conversation_id: UUID,
    body: ConversationAttachmentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationAttachmentResponse:
    """Attach a drive file to a conversation."""
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=current_user.id,  # type: ignore
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Verify drive file ownership
    stmt = select(DriveFileModel).where(
        DriveFileModel.id == body.drive_file_id,
        DriveFileModel.user_id == current_user.id,
        DriveFileModel.is_deleted == False,  # noqa: E712
    )
    df_result = await session.exec(stmt)
    drive_file = df_result.first()
    if not drive_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drive file not found or not accessible",
        )

    attachment = await service.attach_drive_file(
        session,
        conversation_id=conversation.id,  # type: ignore
        drive_file_id=drive_file.id,  # type: ignore
    )
    return ConversationAttachmentResponse(
        id=attachment.id,  # type: ignore
        conversation_id=attachment.conversation_id,
        drive_file_id=attachment.drive_file_id,
        attached_at=attachment.attached_at,
    )


@router.delete(
    "/conversations/{conversation_id}/attachments/{drive_file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_file_from_conversation(
    conversation_id: UUID,
    drive_file_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    """Detach a drive file from a conversation."""
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=current_user.id,  # type: ignore
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    stmt = select(DriveFileModel).where(
        DriveFileModel.id == drive_file_id,
        DriveFileModel.user_id == current_user.id,
        DriveFileModel.is_deleted == False,  # noqa: E712
    )
    df_result = await session.exec(stmt)
    if not df_result.first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drive file not found or not accessible",
        )

    await service.detach_drive_file(
        session,
        conversation_id=conversation.id,  # type: ignore
        drive_file_id=drive_file_id,
    )
