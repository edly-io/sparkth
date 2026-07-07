from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
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
    documents = await service.list_conversation_attachments(
        session,
        conversation_id=cast(int, conversation.id),
    )
    return [
        AttachedDocumentResponse(
            id=cast(int, document.id),
            name=document.name,
            size=None,
        )
        for document in documents
    ]


@router.post(
    "/conversations/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationAttachmentResponse,
)
async def attach_document_to_conversation(
    body: ConversationAttachmentCreate,
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationAttachmentResponse:
    document = await service.get_user_owned_document(
        session,
        document_id=body.document_id,
        user_id=cast(int, current_user.id),
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or not accessible",
        )
    attachment = await service.attach_document(
        session,
        conversation_id=cast(int, conversation.id),
        document_id=cast(int, document.id),
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
    conversation: Conversation = Depends(get_owned_conversation),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    document = await service.get_user_owned_document(
        session,
        document_id=document_id,
        user_id=cast(int, current_user.id),
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or not accessible",
        )
    await service.detach_document(
        session,
        conversation_id=cast(int, conversation.id),
        document_id=document_id,
    )
