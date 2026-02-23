import json
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.core.logger import get_logger
from app.core_plugins.chat.cache import get_cache_service
from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.encryption import get_encryption_service
from app.core_plugins.chat.models import Message, ProviderAPIKey
from app.core_plugins.chat.providers import BaseChatProvider, get_provider
from app.core_plugins.chat.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    ProviderAPIKeyCreate,
    ProviderAPIKeyListResponse,
    ProviderAPIKeyResponse,
    ToolListResponse,
    ToolSchema,
)
from app.core_plugins.chat.service import ChatService
from app.core_plugins.chat.tools import get_tool_registry
from app.models.user import User

logger = get_logger(__name__)

chat_router = APIRouter(prefix="/chat", tags=["Chat"])


@lru_cache
def get_chat_system_config() -> ChatSystemConfig:
    """Dependency to get chat system configuration from environment variables."""
    return ChatSystemConfig()


def get_chat_service(config: ChatSystemConfig = Depends(get_chat_system_config)) -> ChatService:
    """Dependency to get chat service with encryption and cache."""
    encryption = get_encryption_service(config.encryption_key)
    cache = get_cache_service(config.redis_url, config.redis_key_ttl)
    return ChatService(encryption, cache)


@chat_router.post("/keys", response_model=ProviderAPIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: ProviderAPIKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ProviderAPIKeyResponse:
    try:
        db_key = await service.create_api_key(
            session=session,
            user_id=current_user.id,  # type: ignore
            provider=key_data.provider,
            api_key=key_data.api_key,
        )

        return ProviderAPIKeyResponse(
            id=db_key.id,  # type: ignore
            provider=db_key.provider,
            is_active=db_key.is_active,
            created_at=db_key.created_at,
            last_used_at=db_key.last_used_at,
        )
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key",
        )


@chat_router.get("/keys", response_model=ProviderAPIKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ProviderAPIKeyListResponse:
    keys = await service.list_api_keys(session, current_user.id)  # type: ignore

    return ProviderAPIKeyListResponse(
        keys=[
            ProviderAPIKeyResponse(
                id=key.id,  # type: ignore
                provider=key.provider,
                is_active=key.is_active,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
            )
            for key in keys
        ],
        total=len(keys),
    )


@chat_router.put("/keys/{key_id}", response_model=ProviderAPIKeyResponse)
async def update_api_key(
    key_id: int,
    key_update: ProviderAPIKeyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> Any:
    """Update an existing API key."""
    result = await session.exec(
        select(ProviderAPIKey)
        .where(ProviderAPIKey.id == key_id)
        .where(ProviderAPIKey.user_id == current_user.id)
        .where(ProviderAPIKey.deleted_at == None)
    )
    key = result.first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    if key.provider != key_update.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change provider for existing key. Delete and create a new one instead.",
        )

    encrypted_key = service.encryption.encrypt(key_update.api_key)
    key.encrypted_key = encrypted_key
    key.update_timestamp()

    session.add(key)
    await session.commit()
    await session.refresh(key)

    cache_key = service.cache.make_key("api_key", str(current_user.id), key.provider)
    await service.cache.set(cache_key, key_update.api_key)

    logger.info(f"Updated API key {key_id} for user {current_user.id}")

    return ProviderAPIKeyResponse(
        id=key.id,  # type: ignore
        provider=key.provider,
        is_active=key.is_active,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
    )


@chat_router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    deleted = await service.delete_api_key(
        session=session,
        user_id=current_user.id,  # type: ignore
        key_id=key_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )


@chat_router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> Any:
    api_key = await service.get_api_key(
        session=session,
        user_id=current_user.id,  # type: ignore
        provider=request.provider,
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No API key found for provider: {request.provider}",
        )

    conversation_id = request.conversation_id

    if conversation_id:
        conversation = await service.get_conversation(
            session=session,
            conversation_id=conversation_id,
            user_id=current_user.id,  # type: ignore
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_id} not found",
            )
    else:
        stmt = select(ProviderAPIKey).where(
            ProviderAPIKey.user_id == current_user.id,
            ProviderAPIKey.provider == request.provider,
            ProviderAPIKey.is_active == True,  # noqa: E712
            ProviderAPIKey.deleted_at == None,
        )
        result = await session.exec(stmt)
        api_key_record = result.first()

        conversation = await service.create_conversation(
            session=session,
            user_id=current_user.id,  # type: ignore
            api_key_id=api_key_record.id if api_key_record else None,  # type: ignore
            provider=request.provider,
            model=request.model,
        )

    for msg in request.messages:
        await service.add_message(
            session=session,
            conversation_id=conversation.id,  # type: ignore
            role=msg.role,
            content=msg.content,
            message_type="attachment" if msg.attachment else "text",
            attachment_name=msg.attachment.name if msg.attachment else None,
            attachment_size=msg.attachment.size if msg.attachment else None,
        )

    db_messages = await service.get_conversation_messages(
        session=session,
        conversation_id=conversation.id,  # type: ignore
    )
    messages = [{"role": m.role, "content": m.content} for m in db_messages]

    try:
        provider = get_provider(
            provider_name=request.provider,
            api_key=api_key,
            model=request.model,
            temperature=request.temperature,
        )

        tool_registry = get_tool_registry()
        tools = None

        if request.tools == "none" or request.tools == []:
            logger.info("Tools explicitly disabled")
            tools = None
        elif request.tools == "*" or request.tools == "all":
            tools = await tool_registry.get_all_tools()
            logger.info(f"Auto-including all {len(tools)} available tools (default)")
        elif request.tools and isinstance(request.tools, list):
            tools = await tool_registry.get_tools_by_names(request.tools)
            if not tools:
                logger.warning(f"No tools found for: {request.tools}")

        if tools and request.include_system_tools_message:
            tool_descriptions = [f"- {tool.name}: {tool.description}" for tool in tools]
            tool_list_message = "You have access to the following tools:\n" + "\n".join(tool_descriptions)
            messages.insert(0, {"role": "system", "content": tool_list_message})

        if request.stream:
            return StreamingResponse(
                stream_chat_response(
                    provider=provider,
                    messages=messages,
                    conversation_id=conversation.id,  # type: ignore
                    service=service,
                    session=session,
                    tools=tools,
                ),
                media_type="text/event-stream",
            )
        else:
            response = await provider.send_message(
                messages=messages,
                max_tokens=request.max_tokens,
                tools=tools,
            )

            tokens_used = response.get("metadata", {}).get("usage_metadata", {}).get("total_tokens")
            tool_calls = response.get("tool_calls")

            await service.add_message(
                session=session,
                conversation_id=conversation.id,  # type: ignore
                role="assistant",
                content=response["content"],
                tokens_used=tokens_used,
                metadata=response.get("metadata"),
                message_type="text",
            )

            return ChatCompletionResponse(
                message=ChatMessage(
                    role="assistant",
                    content=response["content"],
                ),
                conversation_id=conversation.id,  # type: ignore
                model=request.model,
                provider=request.provider,
                tokens_used=tokens_used,
                tool_calls=tool_calls,
                metadata=response.get("metadata", {}),
            )

    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat completion failed",
        )


async def stream_chat_response(
    provider: BaseChatProvider,
    messages: list[dict[str, str]],
    conversation_id: int,
    service: ChatService,
    session: AsyncSession,
    tools: list[Any] | None = None,
) -> Any:
    full_response = ""

    try:
        async for token in provider.stream_message(messages, tools=tools):
            full_response += token
            data = json.dumps({"token": token, "done": False})
            yield f"data: {data}\n\n"

        assistant_message = await service.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
        )

        data = json.dumps(
            {
                "token": "",
                "done": True,
                "conversation_id": conversation_id,
                "message": {
                    "id": assistant_message.id,
                    "role": "assistant",
                    "content": full_response,
                    "message_type": "text",
                    "attachment_name": None,
                    "attachment_size": None,
                },
            }
        )
        yield f"data: {data}\n\n"

    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        await service.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content="An error occurred while generating a response. Please try again.",
            is_error=True,
        )
        error_data = json.dumps({"error": str(e), "done": True})
        yield f"data: {error_data}\n\n"


@chat_router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationListResponse:
    conversations, total = await service.list_conversations(
        session=session,
        user_id=current_user.id,  # type: ignore
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
            id=conv.id,  # type: ignore
            provider=conv.provider,
            model=conv.model,
            title=conv.title,
            total_tokens_used=conv.total_tokens_used,
            total_cost=conv.total_cost,
            message_count=message_counts.get(conv.id, 0),  # type: ignore
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]

    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
    )


@chat_router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> ConversationDetailResponse:
    conversation = await service.get_conversation(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,  # type: ignore
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages = await service.get_conversation_messages(
        session=session, conversation_id=conversation_id, limit=limit, offset=offset
    )

    message_count = len(messages)

    return ConversationDetailResponse(
        id=conversation.id,  # type: ignore
        provider=conversation.provider,
        model=conversation.model,
        title=conversation.title,
        total_tokens_used=conversation.total_tokens_used,
        total_cost=conversation.total_cost,
        message_count=message_count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(
                id=msg.id,  # type: ignore
                role=msg.role,
                content=msg.content,
                tokens_used=msg.tokens_used,
                cost=msg.cost,
                created_at=msg.created_at,
                message_type=msg.message_type,
                attachment_name=msg.attachment_name,
                attachment_size=msg.attachment_size,
            )
            for msg in messages
        ],
    )


def get_parameters_schema(args_schema: type[BaseModel] | dict[str, Any] | None) -> dict[str, Any]:
    if args_schema is None:
        return {}
    if isinstance(args_schema, dict):
        return args_schema
    return args_schema.model_json_schema()


@chat_router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    current_user: User = Depends(get_current_user),
) -> ToolListResponse:
    """List all available tools from loaded plugins."""
    tool_registry = get_tool_registry()
    tools = await tool_registry.get_all_tools()

    tool_schemas = [
        ToolSchema(
            name=tool.name,
            description=tool.description or "",
            parameters=get_parameters_schema(tool.args_schema),
        )
        for tool in tools
    ]

    return ToolListResponse(
        tools=tool_schemas,
        total=len(tool_schemas),
    )
