from typing import Any, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.classifier import HistoryTurn
from app.core_plugins.chat.config import ChatSettings, get_chat_settings
from app.core_plugins.chat.constants import LLM_PROVIDER_API_ERRORS
from app.core_plugins.chat.exceptions import RAGIntentRouterError
from app.core_plugins.chat.lms_credentials import build_lms_credentials_message
from app.core_plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt
from app.core_plugins.chat.routes.utils import (
    attach_request_documents,
    classify_in_scope,
    extract_query_text,
    get_or_create_conversation,
    persist_incoming_messages,
    persist_pre_stream_error,
    resolve_document_blocks,
    resolve_rag_intent,
    resolve_tools,
    stream_out_of_scope_refusal,
)
from app.core_plugins.chat.routes.utils.stream_processor import ChatStreamProcessor, streaming_error_message
from app.core_plugins.chat.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage
from app.core_plugins.chat.service import ChatService, get_chat_service
from app.core_plugins.chat.tools import get_tool_registry
from app.lib.db import get_async_session
from app.lib.llm import (
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    get_llm_service,
    get_provider,
)
from app.lib.log import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter()


# The handler returns ChatCompletionResponse (stream=false) or an SSE
# StreamingResponse (stream=true); response_model alone cannot express that
# union, so the 200 response declares both content types explicitly.
@router.post(
    "/completions",
    response_model=None,
    responses={
        200: {
            "model": ChatCompletionResponse,
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def chat_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
    llm_service: LLMConfigService = Depends(get_llm_service),
    config: ChatSettings = Depends(get_chat_settings),
) -> Any:
    user_id: int = cast(int, current_user.id)
    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=user_id,
            config_id=request.llm_config_id,
        )
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = "No AI Key found for the current user. Please configure an AI key in your chat plugin settings."
        await persist_pre_stream_error(session, service, request, user_id, detail)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except LLMConfigModelNotSetError as exc:
        logger.warning("LLMConfig %s has no model set: %s", request.llm_config_id, exc)
        detail = "The selected AI key has no model configured. Go to AI Keys to set a model before chatting."
        await persist_pre_stream_error(session, service, request, user_id, detail)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except LLMConfigInactiveError as exc:
        logger.warning("LLMConfig %s is inactive for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = (
            "The selected AI key is deactivated. Go to AI Keys to reactivate it,"
            "or choose a different one in chat settings."
        )
        await persist_pre_stream_error(session, service, request, user_id, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model
    conversation_uuid = request.conversation_id
    query_text = extract_query_text(request.messages)

    # Runs before any DB writes so an out-of-scope first message leaves no trace.
    _skip_main_scope_check = False
    if not conversation_uuid:
        if not await classify_in_scope(query_text, provider_name, api_key, [], None):
            if request.stream:
                return StreamingResponse(
                    stream_out_of_scope_refusal(),
                    media_type="text/event-stream",
                )
            return ChatCompletionResponse(
                message=ChatMessage(role="assistant", content=REFUSAL_MESSAGE),
                conversation_id=None,
                model=model,
                provider=provider_name,
            )
        _skip_main_scope_check = True

    conversation = await get_or_create_conversation(
        session=session,
        service=service,
        conversation_uuid=conversation_uuid,
        user_id=user_id,
        messages=request.messages,
        llm_config_id=request.llm_config_id,
        provider_name=provider_name,
        api_key=api_key,
        model=model,
        config=config,
        background_tasks=background_tasks,
    )

    if request.document_ids:
        await attach_request_documents(
            session,
            service,
            request.document_ids,
            user_id,
            cast(int, conversation.id),
        )
    await persist_incoming_messages(session, service, request.messages, cast(int, conversation.id))

    db_messages = await service.get_conversation_messages(
        session=session,
        conversation_id=cast(int, conversation.id),
    )

    try:
        # Fetch conversation attachments early — needed by both the scope classifier
        # (to know documents are in play) and the RAG intent router.
        attached_documents = await service.list_conversation_attachments(
            session=session,
            conversation_id=cast(int, conversation.id),
        )
        attached_document_names = [document.name for document in attached_documents]

        if not _skip_main_scope_check:
            prior_history: list[HistoryTurn] = [
                {"role": cast(Literal["user", "assistant"], m.role), "content": m.content}
                for m in db_messages
                if m is not db_messages[-1] or not (m.role == "user" and m.content == query_text)
            ]
            _in_scope = await classify_in_scope(
                query_text, llm_config.provider, api_key, prior_history, attached_document_names or None
            )
        else:
            _in_scope = True

        if not _in_scope:
            await service.add_message(
                session=session,
                conversation_id=cast(int, conversation.id),
                role="assistant",
                content=REFUSAL_MESSAGE,
                message_type="text",
            )
            if request.stream:
                return StreamingResponse(
                    stream_out_of_scope_refusal(),
                    media_type="text/event-stream",
                )
            return ChatCompletionResponse(
                message=ChatMessage(role="assistant", content=REFUSAL_MESSAGE),
                conversation_id=conversation.uuid,
                model=llm_config.model,
                provider=llm_config.provider,
            )

        provider = get_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            system_prompt=get_learning_design_system_prompt(),
            temperature=request.temperature,
            max_tool_executions=config.max_tool_executions,
        )

        # --- RAG Intent Routing: decide whether to retrieve context from attachments ---
        # attached_documents already fetched above for the scope check
        should_run_rag, rag_routing_reason = await resolve_rag_intent(attached_documents, query_text, provider)

        # Use DB messages for history, but replace the current batch with original
        # request content to preserve content blocks (e.g. base64 document attachments).
        num_current = len(request.messages)
        history: list[dict[str, Any]] = (
            [{"role": m.role, "content": m.content} for m in db_messages[:-num_current]]
            if len(db_messages) > num_current
            else []
        )

        unresolved_messages: list[ChatMessage] | None = None
        if should_run_rag and attached_documents:
            # Synthetic message: document blocks (for RAG resolution) + user's query text
            # so that extract_query_text finds the question and the user's question is
            # preserved in current after resolution.
            document_blocks: list[dict[str, Any]] = [
                {"type": "drive_file", "file_id": document.id} for document in attached_documents
            ]
            text_block: list[dict[str, Any]] = [{"type": "text", "text": query_text}] if query_text else []
            unresolved_messages = [ChatMessage(role="user", content=document_blocks + text_block)]

        if request.stream and should_run_rag:
            # Pass synthetic messages as current so the in-stream assembly pass finds the
            # legacy document blocks to replace. The query text block travels with them so the
            # LLM sees both the RAG context and the user's question after replacement.
            if unresolved_messages is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Chat completion failed",
                )
            current: list[dict[str, Any]] = [{"role": msg.role, "content": msg.content} for msg in unresolved_messages]
        else:
            if should_run_rag and unresolved_messages:
                # resolve_document_blocks replaces legacy document blocks with RAG context;
                # the query text block is preserved alongside it.
                resolved_messages = await resolve_document_blocks(
                    messages=unresolved_messages,
                    llm=provider.create_llm(),
                )
            else:
                resolved_messages = request.messages
            current = [{"role": msg.role, "content": msg.content} for msg in resolved_messages]

        messages = history + current

        tools = await resolve_tools(request, get_tool_registry())
        if tools and request.include_system_tools_message:
            tool_descriptions = [f"- {tool.name}: {tool.description}" for tool in tools]
            tool_list_message = "You have access to the following tools:\n" + "\n".join(tool_descriptions)
            messages.insert(0, {"role": "system", "content": tool_list_message})

        lms_credentials_message = await build_lms_credentials_message(
            session=session,
            user_id=user_id,
            tools=tools,
        )
        if lms_credentials_message:
            provider.system_prompt += f"\n\n{lms_credentials_message}"

        if request.stream:
            # The RAG inputs are only meaningful when the router decided to retrieve;
            # gate them together so an unused create_llm() call is never made.
            rag_unresolved = unresolved_messages if should_run_rag else None
            rag_user_id = user_id if should_run_rag else None
            rag_llm = provider.create_llm() if should_run_rag else None
            processor = ChatStreamProcessor(
                provider,
                messages,
                conversation,
                service,
                tools,
                rag_unresolved,
                rag_user_id,
                rag_llm,
                should_run_rag,
                rag_routing_reason,
            )
            return StreamingResponse(
                processor.stream(),
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
                conversation_id=cast(int, conversation.id),
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
                conversation_id=conversation.uuid,
                model=model,
                provider=provider_name,
                tokens_used=tokens_used,
                tool_calls=tool_calls,
                metadata=response.get("metadata", {}),
            )

    except RAGIntentRouterError as e:
        logger.error("RAG intent router failed for user %s conversation %s: %s", current_user.id, conversation.id, e)
        detail = "Failed to determine retrieval intent. Please try again."
        if conversation.id is not None:
            await service.add_message(
                session=session,
                conversation_id=conversation.id,
                role="assistant",
                content=detail,
                is_error=True,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from e
    except LLM_PROVIDER_API_ERRORS as e:
        logger.error("Provider API error: %s", e)
        detail = streaming_error_message(e)
        if conversation.id is not None:
            await service.add_message(
                session=session,
                conversation_id=conversation.id,
                role="assistant",
                content=detail,
                is_error=True,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from e
    except (ValueError, RuntimeError, ValidationError, LangChainException) as e:
        logger.error("Chat completion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat completion failed",
        ) from e
