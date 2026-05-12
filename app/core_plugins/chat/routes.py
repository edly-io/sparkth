import json
import re
from functools import lru_cache
from typing import Any, AsyncGenerator, Literal, cast
from uuid import UUID

import anthropic
import httpx
import openai
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from google.api_core import exceptions as google_exceptions
from langchain_core.exceptions import LangChainException
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.core.logger import get_logger
from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.conversation_title import (
    extract_title_from_messages,
    generate_conversation_title,
    get_first_user_text,
)
from app.core_plugins.chat.lms_credentials import build_lms_credentials_message
from app.core_plugins.chat.models import Conversation, Message
from app.core_plugins.chat.schemas import (
    ActiveDriveFile,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    ToolListResponse,
    ToolSchema,
)
from app.core_plugins.chat.service import ChatService
from app.core_plugins.chat.tools import get_tool_registry
from app.llm.classifier import HistoryTurn, ScopeClassifier
from app.llm.exceptions import LLMConfigInactiveError, LLMConfigModelNotSetError, LLMConfigNotFoundError
from app.llm.prompt import REFUSAL_MESSAGE, is_query_in_scope
from app.llm.providers import (
    BaseChatProvider,
    get_provider,
)
from app.llm.service import LLMConfigService, get_llm_service
from app.models.drive import DriveFile as DriveFileModel
from app.models.user import User
from app.rag.context_service import RAGContextService
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.provider import get_provider as get_rag_provider
from app.rag.types import RAGContext
from app.rag.utils import get_asset

logger = get_logger(__name__)

_RAG_CONTEXT_PROMPT = get_asset("rag_context_replacement_prompt", "txt")
if not isinstance(_RAG_CONTEXT_PROMPT, str):
    raise TypeError("rag_context_replacement_prompt asset must be a string")

chat_router = APIRouter(prefix="/chat", tags=["Chat"])


_PROVIDER_API_ERRORS = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.RateLimitError,
    anthropic.BadRequestError,
    anthropic.APIStatusError,
    anthropic.APIConnectionError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.RateLimitError,
    openai.BadRequestError,
    openai.APIStatusError,
    openai.APIConnectionError,
    google_exceptions.Unauthenticated,
    google_exceptions.PermissionDenied,
    google_exceptions.ResourceExhausted,
    google_exceptions.InvalidArgument,
    google_exceptions.GoogleAPICallError,
    google_exceptions.ServiceUnavailable,
    httpx.RemoteProtocolError,
)


@lru_cache
def get_chat_system_config() -> ChatSystemConfig:
    """Dependency to get chat system configuration from environment variables."""
    return ChatSystemConfig()


def get_chat_service() -> ChatService:
    """Dependency to get chat service."""
    return ChatService()


def get_rag_context_service() -> RAGContextService:
    """FastAPI dependency: returns a stateless RAGContextService."""
    return RAGContextService(embedding_provider=get_rag_provider())


async def _stream_out_of_scope_refusal() -> AsyncGenerator[str, None]:
    """Yield a single SSE done-event carrying the refusal message as content."""
    yield f"data: {json.dumps({'done': True, 'content': REFUSAL_MESSAGE})}\n\n"


def _strip_md(text: str) -> str:
    """Remove markdown emphasis markers (* and **) from a string."""
    return re.sub(r"\*+", "", text).strip()


def _parse_rag_sections(model_metadata: str | None) -> list[dict[str, Any]] | None:
    if not model_metadata:
        return None
    try:
        meta = json.loads(model_metadata)
        sections = meta.get("rag_sections")
        return sections if isinstance(sections, list) else None
    except (json.JSONDecodeError, AttributeError):
        return None


def _extract_query_text(messages: list[ChatMessage]) -> str:
    """Extract the user's plain text from the last user message for RAG query embedding."""
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        if isinstance(msg.content, str):
            return msg.content.strip()
        text_parts = [
            block.get("text", "") for block in msg.content if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = " ".join(text_parts).strip()
        if joined:
            return joined
    return ""


async def _resolve_drive_file_blocks(
    messages: list[ChatMessage],
    session: AsyncSession,
    user_id: int,
    rag_service: RAGContextService,
    llm: Any,
) -> list[ChatMessage]:
    """Replace drive_file content blocks with RAG context text blocks.

    Returns a new list; original messages are not mutated.
    Base64 and plain text blocks pass through unchanged.

    Raises:
        HTTPException(422): file not found, not owned, or RAG not ready.
        HTTPException(500): embedding or similarity search failure.
    """
    query_text = _extract_query_text(messages)
    resolved: list[ChatMessage] = []

    for msg in messages:
        if not isinstance(msg.content, list):
            resolved.append(msg)
            continue

        has_drive_file = any(isinstance(b, dict) and b.get("type") == "drive_file" for b in msg.content)
        if not has_drive_file:
            resolved.append(msg)
            continue

        non_file_blocks: list[dict[str, Any]] = []
        rag_blocks: list[dict[str, Any]] = []
        for block in msg.content:
            if not isinstance(block, dict) or block.get("type") != "drive_file":
                non_file_blocks.append(block)
                continue

            raw_id = block.get("file_id")
            if raw_id is None:
                logger.warning("Skipping drive_file block missing file_id: %s", block)
                continue
            file_id: int = int(raw_id)
            try:
                context = await rag_service.get_context_via_agent(
                    session=session,
                    user_id=user_id,
                    file_db_id=file_id,
                    query=query_text,
                    llm=llm,
                )
                if context.chunks:
                    rag_blocks.append({"type": "text", "text": context.formatted_text})
                logger.info(
                    "Replaced drive_file block file_id=%d with %d RAG chunks",
                    file_id,
                    len(context.chunks),
                )
            except DriveFileNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"File (id={file_id}) not found or not accessible.",
                ) from exc
            except RAGNotReadyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"File (id={file_id}) is still being processed "
                        f"(status: {exc.rag_status}). Please wait and try again."
                    ),
                ) from exc
            except RAGRetrievalError as exc:
                logger.error("RAG retrieval error for file_id=%d: %s", file_id, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve document context. Please try again.",
                ) from exc

        if rag_blocks:
            user_text_blocks = [b for b in non_file_blocks if isinstance(b, dict) and b.get("type") == "text"]
            other_blocks = [b for b in non_file_blocks if not (isinstance(b, dict) and b.get("type") == "text")]
            new_blocks: list[dict[str, Any]] = (
                [{"type": "text", "text": _RAG_CONTEXT_PROMPT}] + other_blocks + rag_blocks + user_text_blocks
            )
        else:
            new_blocks = non_file_blocks
        resolved.append(ChatMessage(role=msg.role, content=new_blocks, attachment=msg.attachment))

    return resolved


def _extract_drive_file_id_from_messages(messages: list[ChatMessage]) -> int | None:
    """Extract the first drive_file file_id from message content blocks."""
    for msg in messages:
        if not isinstance(msg.content, list):
            continue
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "drive_file":
                raw_id = block.get("file_id")
                if raw_id is not None:
                    return int(raw_id)
    return None


def _extract_all_drive_file_ids_from_messages(messages: list[ChatMessage]) -> list[int]:
    """Extract all unique drive_file file_ids from message content blocks, preserving order."""
    seen: set[int] = set()
    result: list[int] = []
    for msg in messages:
        if not isinstance(msg.content, list):
            continue
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "drive_file":
                raw_id = block.get("file_id")
                if raw_id is not None:
                    file_id = int(raw_id)
                    if file_id not in seen:
                        seen.add(file_id)
                        result.append(file_id)
    return result


async def _persist_pre_stream_error(
    session: AsyncSession,
    service: ChatService,
    request: ChatCompletionRequest,
    user_id: int,
    message: str,
) -> None:
    """Persist an error message to an existing conversation before raising an HTTP error.

    Only called when request.conversation_id is set — new conversations are never
    created here because the failure happened before any conversation was established.
    """
    if not request.conversation_id:
        return
    try:
        conversation = await service.get_conversation_by_uuid(
            session=session,
            uuid=request.conversation_id,
            user_id=user_id,
        )
        if conversation and conversation.id is not None:
            await service.add_message(
                session=session,
                conversation_id=conversation.id,
                role="assistant",
                content=message,
                is_error=True,
            )
    except SQLAlchemyError:
        logger.exception("Failed to persist pre-stream error message for conversation %s", request.conversation_id)


@chat_router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
    llm_service: LLMConfigService = Depends(get_llm_service),
    config: ChatSystemConfig = Depends(get_chat_system_config),
    rag_service: RAGContextService = Depends(get_rag_context_service),
) -> Any:
    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=request.llm_config_id,
        )
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = "No AI Key found for the current user."
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except LLMConfigModelNotSetError as exc:
        logger.warning("LLMConfig %s has no model set: %s", request.llm_config_id, exc)
        detail = "The selected AI key has no model configured. Go to AI Keys to set a model before chatting."
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except LLMConfigInactiveError as exc:
        logger.warning("LLMConfig %s is inactive for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = "The selected AI key is deactivated. Go to AI Keys to reactivate it, or choose a different one in chat settings."
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model

    conversation_uuid = request.conversation_id
    active_drive_file_ids = _extract_all_drive_file_ids_from_messages(request.messages)
    active_drive_file_id = active_drive_file_ids[0] if active_drive_file_ids else None

    if conversation_uuid:
        conversation = await service.get_conversation_by_uuid(
            session=session,
            uuid=conversation_uuid,
            user_id=current_user.id,  # type: ignore
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_uuid} not found",
            )
        if active_drive_file_ids:
            await service.set_active_drive_file(
                session=session,
                conversation_id=conversation.id,  # type: ignore
                user_id=current_user.id,  # type: ignore
                drive_file_id=active_drive_file_id,
                drive_file_ids=active_drive_file_ids,
            )
    else:
        conversation = await service.create_conversation(
            session=session,
            user_id=current_user.id,  # type: ignore
            llm_config_id=request.llm_config_id,
            provider=provider_name,
            model=model,
            title=extract_title_from_messages(request.messages, max_length=config.title_max_length),
            active_drive_file_id=active_drive_file_id,
            active_drive_file_ids=active_drive_file_ids or None,
        )

        first_user_text = get_first_user_text(request.messages)
        if first_user_text:
            background_tasks.add_task(
                generate_conversation_title,
                conversation_id=conversation.id,  # type: ignore
                user_id=current_user.id,  # type: ignore
                first_user_message=first_user_text,
                service=service,
            )

    for msg in request.messages:
        # Store a text summary for messages with content blocks (e.g. file attachments)
        if isinstance(msg.content, list):
            text_parts = [
                block.get("text", "")
                for block in msg.content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            stored_content = " ".join(text_parts) if text_parts else "[File attachment]"
        else:
            stored_content = msg.content
        await service.add_message(
            session=session,
            conversation_id=conversation.id,  # type: ignore
            role=msg.role,
            content=stored_content,
            message_type="attachment" if msg.attachment else "text",
            attachment_name=msg.attachment.name if msg.attachment else None,
            attachment_size=msg.attachment.size if msg.attachment else None,
        )

    has_drive_files = any(
        isinstance(b, dict) and b.get("type") == "drive_file"
        for msg in request.messages
        if isinstance(msg.content, list)
        for b in msg.content
    )

    db_messages = await service.get_conversation_messages(
        session=session,
        conversation_id=conversation.id,  # type: ignore
    )

    try:
        # --- Tiered scope check (plain-text only; drive-file/RAG paths skip entirely) ---
        if not has_drive_files:
            query_text = _extract_query_text(request.messages)
            _in_scope = True
            if query_text:
                # Tier 1: fast keyword pre-filter — catches obvious out-of-scope at zero LLM cost
                if not is_query_in_scope(query_text):
                    _in_scope = False
                else:
                    # Tier 2: LLM classifier for nuanced cases keywords can't handle
                    classifier = ScopeClassifier(provider_name=llm_config.provider, api_key=api_key)
                    prior_history: list[HistoryTurn] = [
                        {"role": cast(Literal["user", "assistant"], m.role), "content": m.content}
                        for m in db_messages
                        if m is not db_messages[-1] or not (m.role == "user" and m.content == query_text)
                    ]
                    _in_scope = await classifier.classify(query_text, history=prior_history)
            if not _in_scope:
                await service.add_message(
                    session=session,
                    conversation_id=conversation.id,  # type: ignore
                    role="assistant",
                    content=REFUSAL_MESSAGE,
                    message_type="text",
                )
                if request.stream:
                    return StreamingResponse(
                        _stream_out_of_scope_refusal(),
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
            temperature=request.temperature,
            max_tool_executions=config.max_tool_executions,
        )

        # Use DB messages for history, but replace current batch with original
        # request content to preserve content blocks (e.g. base64 file attachments)
        num_current = len(request.messages)
        history: list[dict[str, Any]] = (
            [{"role": m.role, "content": m.content} for m in db_messages[:-num_current]]
            if len(db_messages) > num_current
            else []
        )

        if request.stream and has_drive_files:
            # For streaming with drive files, RAG resolution happens in the generator
            current: list[dict[str, Any]] = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        else:
            # For non-streaming, or streaming without drive files, resolve synchronously
            resolved_messages = await _resolve_drive_file_blocks(
                messages=request.messages,
                session=session,
                user_id=current_user.id,  # type: ignore[arg-type]
                rag_service=rag_service,
                llm=provider._create_llm(),
            )
            current = [{"role": msg.role, "content": msg.content} for msg in resolved_messages]

        messages = history + current

        tool_registry = get_tool_registry()
        tools = None

        if request.tools == "none" or request.tools == []:
            logger.info("Tools explicitly disabled")
            tools = None
        elif request.tools == "*" or request.tools == "all":
            tools = await tool_registry.get_all_tools()
            logger.info("Auto-including all %d available tools (default)", len(tools))
        elif request.tools and isinstance(request.tools, list):
            tools = await tool_registry.get_tools_by_names(request.tools)
            if not tools:
                logger.warning("No tools found for: %s", request.tools)

        if tools and request.include_system_tools_message:
            tool_descriptions = [f"- {tool.name}: {tool.description}" for tool in tools]
            tool_list_message = "You have access to the following tools:\n" + "\n".join(tool_descriptions)
            messages.insert(0, {"role": "system", "content": tool_list_message})

        # Mutate system_prompt before the stream branch so both the streaming
        # and non-streaming paths receive the credentials hint.
        lms_credentials_message = await build_lms_credentials_message(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            tools=tools,
        )
        if lms_credentials_message:
            provider.system_prompt += f"\n\n{lms_credentials_message}"

        if request.stream:
            stream_kwargs: dict[str, Any] = {}
            if has_drive_files:
                stream_kwargs = {
                    "unresolved_messages": request.messages,
                    "rag_service": rag_service,
                    "user_id": current_user.id,
                    "similarity_threshold": request.similarity_threshold,
                    "llm": provider._create_llm(),
                }
            return StreamingResponse(
                stream_chat_response(
                    provider=provider,
                    messages=messages,
                    conversation=conversation,
                    service=service,
                    session=session,
                    tools=tools,
                    **stream_kwargs,
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
                conversation_id=conversation.uuid,
                model=model,
                provider=provider_name,
                tokens_used=tokens_used,
                tool_calls=tool_calls,
                metadata=response.get("metadata", {}),
            )

    except _PROVIDER_API_ERRORS as e:
        logger.error(f"Provider API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_streaming_error_message(e),
        )
    except (ValueError, RuntimeError, SQLAlchemyError, ValidationError, LangChainException) as e:
        logger.error("Chat completion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chat completion failed",
        )


async def stream_chat_response(
    provider: BaseChatProvider,
    messages: list[dict[str, Any]],
    conversation: Conversation,
    service: ChatService,
    session: AsyncSession,
    tools: list[Any] | None = None,
    unresolved_messages: list[ChatMessage] | None = None,
    rag_service: RAGContextService | None = None,
    user_id: int | None = None,
    similarity_threshold: float = 0.45,
    llm: Any | None = None,
) -> Any:
    # --- Phase 1: In-stream RAG resolution (emits status events) ---
    confirmed_rag_sections: list[dict[str, str | None]] = []
    if unresolved_messages and rag_service and user_id is not None:
        query_text = _extract_query_text(unresolved_messages)
        files_with_no_results: list[str] = []
        any_results_found = False

        # Collect RAG context per file_id first; assemble messages in one pass after the loop
        # to avoid each iteration overwriting context injected by the previous one.
        rag_context_map: dict[int, RAGContext] = {}

        for msg in unresolved_messages:
            if not isinstance(msg.content, list):
                continue
            for block in msg.content:
                if not isinstance(block, dict) or block.get("type") != "drive_file":
                    continue

                raw_id = block.get("file_id")
                if raw_id is None:
                    logger.warning("Skipping drive_file block missing file_id in stream: %s", block)
                    continue
                file_id: int = int(raw_id)

                yield f"data: {json.dumps({'status': 'searching_document', 'file_id': file_id, 'done': False})}\n\n"

                # --- Agentic RAG: agent selects relevant sections, then similarity search ---
                logger.info("Agentic RAG search for file_id=%d query_len=%d", file_id, len(query_text))
                try:
                    context = await rag_service.get_context_via_agent(
                        session=session,
                        user_id=user_id,
                        file_db_id=file_id,
                        query=query_text,
                        llm=llm,
                    )
                except (DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError) as exc:
                    logger.error("Agentic RAG failed for file_id=%d: %s", file_id, exc)
                    yield f"data: {json.dumps({'error': str(exc), 'done': True})}\n\n"
                    return

                source_name = context.source_name
                results = context.chunks

                if not results:
                    files_with_no_results.append(source_name)
                    continue

                any_results_found = True
                rag_context_map[file_id] = context

                # Build confirmed_rag_sections from retrieved chunks for message metadata
                seen_section_keys: set[str] = set()
                for r in results:
                    chunk = r.chunk
                    label = "subsection" if chunk.subsection else "section" if chunk.section else "chapter"
                    parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
                    name = " / ".join(parts) if parts else "General"
                    key = f"{label}:{name}"
                    if key not in seen_section_keys:
                        seen_section_keys.add(key)
                        confirmed_rag_sections.append({"type": label, "name": name, "source": source_name})

        # Single assembly pass: replace all drive_file blocks at once so that context
        # injected for file₁ is not dropped when file₂ is processed.
        for m in messages:
            if not isinstance(m.get("content"), list):
                continue
            rag_blocks: list[dict[str, Any]] = []
            user_text_blocks: list[dict[str, Any]] = []
            other_blocks: list[dict[str, Any]] = []
            has_drive_file = False
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "drive_file":
                    has_drive_file = True
                    fid = b.get("file_id")
                    if fid is not None and int(fid) in rag_context_map:
                        rag_blocks.append({"type": "text", "text": rag_context_map[int(fid)].formatted_text})
                elif isinstance(b, dict) and b.get("type") == "text":
                    user_text_blocks.append(b)
                else:
                    other_blocks.append(b)
            if not has_drive_file:
                continue
            if rag_blocks:
                m["content"] = (
                    [{"type": "text", "text": _RAG_CONTEXT_PROMPT}] + other_blocks + rag_blocks + user_text_blocks
                )
            else:
                m["content"] = other_blocks + user_text_blocks

        # If every searched file returned no results, surface the no-match message.
        if files_with_no_results and not any_results_found:
            if similarity_threshold <= 0.15:
                no_chunks_msg = (
                    "I searched your documents with progressively less strict matching "
                    "but still couldn't find relevant content for your query.\n\n"
                    "Please try rephrasing your question, or check that your documents contain "
                    "information about this topic."
                )
                done_payload: dict[str, object] = {
                    "done": True,
                    "content": no_chunks_msg,
                    "conversation_id": str(conversation.uuid),
                }
            else:
                source_label = (
                    f"**{files_with_no_results[0]}**" if len(files_with_no_results) == 1 else "your documents"
                )
                no_chunks_msg = (
                    f"I searched {source_label} but couldn't find content closely "
                    f"matching your query.\n\n"
                    f"Please try rephrasing your question, or check that your documents "
                    f"contain information about this topic."
                )
                done_payload = {
                    "done": True,
                    "content": no_chunks_msg,
                    "conversation_id": str(conversation.uuid),
                }
            await service.add_message(
                session=session,
                conversation_id=conversation.id,  # type: ignore[arg-type]
                role="assistant",
                content=no_chunks_msg,
                message_type="text",
            )
            yield f"data: {json.dumps(done_payload)}\n\n"
            return

        yield f"data: {json.dumps({'status': 'generating', 'done': False})}\n\n"

    # --- Phase 2: LLM streaming ---
    full_response = ""
    conversation_id: int = conversation.id  # type: ignore[assignment]

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
            metadata={"rag_sections": confirmed_rag_sections} if confirmed_rag_sections else None,
        )

        data = json.dumps(
            {
                "token": "",
                "done": True,
                "conversation_id": str(conversation.uuid),
                "message": {
                    "id": assistant_message.id,
                    "role": "assistant",
                    "content": full_response,
                    "message_type": "text",
                    "attachment_name": None,
                    "attachment_size": None,
                    "rag_sections": confirmed_rag_sections or None,
                },
            }
        )
        yield f"data: {data}\n\n"

    except _PROVIDER_API_ERRORS as e:
        user_message = _streaming_error_message(e)
        logger.error("Streaming failed: %s", e)
        try:
            logger.info("Persisting provider streaming error for conversation_id=%s", conversation_id)
            await service.add_message(
                session=session,
                conversation_id=conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            logger.info("Provider streaming error persisted for conversation_id=%s", conversation_id)
        except SQLAlchemyError:
            logger.exception("Failed to persist streaming error message for conversation_id=%s", conversation_id)
        error_data = json.dumps({"error": user_message, "done": True})
        yield f"data: {error_data}\n\n"
    except (OSError, LangChainException, SQLAlchemyError) as e:
        logger.exception("Unexpected streaming error: %s", e)
        user_message = "An error occurred while generating a response. Please try again."
        try:
            logger.info("Persisting unexpected streaming error for conversation_id=%s", conversation_id)
            await service.add_message(
                session=session,
                conversation_id=conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            logger.info("Unexpected streaming error persisted for conversation_id=%s", conversation_id)
        except SQLAlchemyError:
            logger.exception("Failed to persist streaming error message for conversation_id=%s", conversation_id)
        error_data = json.dumps({"error": user_message, "done": True})
        yield f"data: {error_data}\n\n"


def _streaming_error_message(exc: Exception) -> str:
    """Map provider API exceptions to concise, user-facing error messages."""
    # Anthropic errors
    if isinstance(exc, anthropic.AuthenticationError):
        return "Invalid API key. Please check your Anthropic API key in AI Keys."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Your Anthropic API key does not have permission to use this model."
    if isinstance(exc, anthropic.RateLimitError):
        return "Anthropic rate limit reached. Please wait a moment and try again."
    if isinstance(exc, anthropic.BadRequestError):
        return "The request was rejected by Anthropic. Please try a different message."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Anthropic API error ({exc.status_code}). Please try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach Anthropic. Please check your network connection."

    # OpenAI errors
    if isinstance(exc, openai.AuthenticationError):
        return "Invalid API key. Please check your OpenAI API key in AI Keys."
    if isinstance(exc, openai.PermissionDeniedError):
        return "Your OpenAI API key does not have permission to use this model."
    if isinstance(exc, openai.RateLimitError):
        return "OpenAI rate limit reached. Please wait a moment and try again."
    if isinstance(exc, openai.BadRequestError):
        return "The request was rejected by OpenAI. Please try a different message."
    if isinstance(exc, openai.APIStatusError):
        return f"OpenAI API error ({exc.status_code}). Please try again."
    if isinstance(exc, openai.APIConnectionError):
        return "Could not reach OpenAI. Please check your network connection."

    # Google errors
    if isinstance(exc, google_exceptions.Unauthenticated):
        return "Invalid API key. Please check your Google API key in AI Keys."
    if isinstance(exc, google_exceptions.PermissionDenied):
        return "Your Google API key does not have permission to use this model."
    if isinstance(exc, google_exceptions.ResourceExhausted):
        return "Google API rate limit reached. Please wait a moment and try again."
    if isinstance(exc, google_exceptions.InvalidArgument):
        return "The request was rejected by Google. Please try a different message."
    if isinstance(exc, google_exceptions.ServiceUnavailable):
        return "Could not reach Google. Please check your network connection."
    if isinstance(exc, google_exceptions.GoogleAPICallError):
        return f"Google API error ({exc.grpc_status_code or 'unknown'}). Please try again."

    # httpx transport errors
    if isinstance(exc, httpx.RemoteProtocolError):
        return "The connection was interrupted. Please try again."

    # Generic fallback
    return "An error occurred while generating a response. Please try again."


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

    all_file_ids: set[int] = set()
    for conv in conversations:
        if conv.active_drive_file_ids:
            all_file_ids.update(json.loads(conv.active_drive_file_ids))
        elif conv.active_drive_file_id:
            all_file_ids.add(conv.active_drive_file_id)

    drive_file_names: dict[int, str] = {}
    if all_file_ids:
        df_stmt = select(DriveFileModel).where(col(DriveFileModel.id).in_(list(all_file_ids)))
        df_result = await session.execute(df_stmt)
        for df in df_result.scalars().all():
            drive_file_names[df.id] = df.name

    def _build_active_files(conv: Conversation) -> list[ActiveDriveFile]:
        if conv.active_drive_file_ids:
            ids: list[int] = json.loads(conv.active_drive_file_ids)
            return [ActiveDriveFile(id=fid, name=drive_file_names[fid]) for fid in ids if fid in drive_file_names]
        if conv.active_drive_file_id and conv.active_drive_file_id in drive_file_names:
            return [ActiveDriveFile(id=conv.active_drive_file_id, name=drive_file_names[conv.active_drive_file_id])]
        return []

    conversation_responses = [
        ConversationResponse(
            id=conv.uuid,
            provider=conv.provider,
            model=conv.model,
            title=conv.title,
            total_tokens_used=conv.total_tokens_used,
            total_cost=conv.total_cost,
            message_count=message_counts.get(conv.id, 0),  # type: ignore
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            active_drive_file_id=conv.active_drive_file_id,
            active_drive_file_name=drive_file_names.get(conv.active_drive_file_id)
            if conv.active_drive_file_id
            else None,
            active_drive_files=_build_active_files(conv),
        )
        for conv in conversations
    ]

    return ConversationListResponse(
        conversations=conversation_responses,
        total=total,
    )


@chat_router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
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
        user_id=current_user.id,  # type: ignore
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages = await service.get_conversation_messages(
        session=session,
        conversation_id=conversation.id,  # type: ignore
        limit=limit,
        offset=offset,
        exclude_errors=False,
    )

    message_count = len(messages)

    active_drive_file_name = None
    active_drive_files_list: list[ActiveDriveFile] = []

    if conversation.active_drive_file_ids:
        ids: list[int] = json.loads(conversation.active_drive_file_ids)
        if ids:
            df_result = await session.execute(select(DriveFileModel).where(col(DriveFileModel.id).in_(ids)))
            df_map = {df.id: df.name for df in df_result.scalars().all()}
            active_drive_files_list = [ActiveDriveFile(id=fid, name=df_map[fid]) for fid in ids if fid in df_map]
            if active_drive_files_list:
                active_drive_file_name = active_drive_files_list[0].name
    elif conversation.active_drive_file_id:
        df_result = await session.execute(
            select(DriveFileModel).where(DriveFileModel.id == conversation.active_drive_file_id)
        )
        df = df_result.scalars().first()
        if df:
            active_drive_file_name = df.name
            active_drive_files_list = [ActiveDriveFile(id=conversation.active_drive_file_id, name=df.name)]

    return ConversationDetailResponse(
        id=conversation.uuid,
        provider=conversation.provider,
        model=conversation.model,
        title=conversation.title,
        total_tokens_used=conversation.total_tokens_used,
        total_cost=conversation.total_cost,
        message_count=message_count,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        active_drive_file_id=conversation.active_drive_file_id,
        active_drive_file_name=active_drive_file_name,
        active_drive_files=active_drive_files_list,
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
                rag_sections=_parse_rag_sections(msg.model_metadata),
                is_error=msg.is_error,
            )
            for msg in messages
        ],
    )


@chat_router.delete("/conversations/{conversation_id}/active-file", status_code=status.HTTP_204_NO_CONTENT)
async def clear_active_drive_file(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
) -> None:
    """Clear the active drive file attachment for a conversation."""
    conversation = await service.get_conversation_by_uuid(
        session=session,
        uuid=conversation_id,
        user_id=current_user.id,  # type: ignore
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    await service.set_active_drive_file(
        session=session,
        conversation_id=conversation.id,  # type: ignore
        user_id=current_user.id,  # type: ignore
        drive_file_id=None,
        drive_file_ids=[],
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
