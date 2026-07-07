from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger
from sparkth.models.user import User
from sparkth.plugins.chat.models import Message
from sparkth.plugins.chat.routes.utils import parse_metadata_list
from sparkth.plugins.chat.schemas import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)
from sparkth.plugins.chat.service import ChatService, get_chat_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationListResponse:
    conversations, total = await service.list_conversations(
        session=session,
        user_id=cast(int, current_user.id),
        limit=limit,
        offset=offset,
    )

    conv_ids = [conv.id for conv in conversations]

    count_stmt = (
        select(Message.conversation_id, func.count(col(Message.id)).label("message_count"))
        .where(col(Message.conversation_id).in_(conv_ids))
        .group_by(col(Message.conversation_id))
    )
    count_result = await session.exec(count_stmt)
    message_counts = {row[0]: row[1] for row in count_result.all()}

    conversation_responses = [
        ConversationResponse(
            id=conv.uuid,
            provider=conv.provider,
            model=conv.model,
            title=conv.title,
            total_tokens_used=conv.total_tokens_used,
            total_cost=conv.total_cost,
            message_count=message_counts.get(cast(int, conv.id), 0),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]

    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationDetailResponse:
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=cast(int, current_user.id),
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages = await service.get_conversation_messages(
        session=session,
        conversation_id=cast(int, conversation.id),
        limit=limit,
        offset=offset,
        exclude_errors=False,
    )

    message_responses = [
        MessageResponse(
            id=cast(int, msg.id),
            role=msg.role,
            content=msg.content,
            tokens_used=msg.tokens_used,
            cost=msg.cost,
            created_at=msg.created_at,
            message_type=msg.message_type,
            attachment_name=msg.attachment_name,
            attachment_size=msg.attachment_size,
            rag_sections=parse_metadata_list(msg.model_metadata, "rag_sections"),
            tool_calls=parse_metadata_list(msg.model_metadata, "tool_calls"),
            is_error=msg.is_error,
        )
        for msg in messages
    ]

    return ConversationDetailResponse(
        id=conversation.uuid,
        provider=conversation.provider,
        model=conversation.model,
        title=conversation.title,
        total_tokens_used=conversation.total_tokens_used,
        total_cost=conversation.total_cost,
        message_count=len(message_responses),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=message_responses,
    )


@router.get(
    "/conversations/{conversation_id}/last-message",
    response_model=MessageResponse | None,
)
async def get_last_conversation_message(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> MessageResponse | None:
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=cast(int, current_user.id),
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = await service.get_last_conversation_message(
        session=session,
        conversation_id=cast(int, conversation.id),
    )
    if msg is None:
        return None

    return MessageResponse(
        id=cast(int, msg.id),
        role=msg.role,
        content=msg.content,
        tokens_used=msg.tokens_used,
        cost=msg.cost,
        created_at=msg.created_at,
        message_type=msg.message_type,
        attachment_name=msg.attachment_name,
        attachment_size=msg.attachment_size,
        rag_sections=parse_metadata_list(msg.model_metadata, "rag_sections"),
        tool_calls=parse_metadata_list(msg.model_metadata, "tool_calls"),
        is_error=msg.is_error,
    )
