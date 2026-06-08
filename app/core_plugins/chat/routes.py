import asyncio
import json
from functools import lru_cache
from pathlib import Path
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
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.conversation_title import (
    extract_title_from_messages,
    generate_conversation_title,
    get_first_user_text,
)
from app.core_plugins.chat.intent_router import RAGIntentRouter, RAGIntentRouterError
from app.core_plugins.chat.lms_credentials import build_lms_credentials_message
from app.core_plugins.chat.models import Conversation, Message
from app.core_plugins.chat.schemas import (
    AttachedDriveFileResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ConversationAttachmentCreate,
    ConversationAttachmentResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    ToolListResponse,
    ToolSchema,
)
from app.core_plugins.chat.service import ChatService
from app.core_plugins.chat.tools import get_tool_registry
from app.lib.db import get_async_session, session_scope
from app.lib.log import get_logger
from app.lib.rag import (
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
)
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

logger = get_logger(__name__)

_RAG_CONTEXT_PROMPT: str = (Path(__file__).parent / "assets" / "rag_context_replacement_prompt.txt").read_text()


def _format_source_block(source_name: str, chunks: list[RetrievedChunk]) -> str:
    """Render one document's retrieved chunks as a prompt text block."""
    lines = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, c in enumerate(chunks, 1):
        parts = [p for p in [c.chapter, c.section, c.subsection] if p]
        label = " / ".join(parts) if parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {label}) ---")
        lines.append(c.content.strip())
        lines.append("")
    return "\n".join(lines)


def _group_by_source(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    """Group retrieved chunks by source_name, preserving first-seen order."""
    grouped: dict[str, list[RetrievedChunk]] = {}
    for c in chunks:
        grouped.setdefault(c.source_name, []).append(c)
    return grouped


def _collect_drive_file_ids(messages: list[ChatMessage]) -> list[int]:
    """Extract all drive_file block file_ids from a list of messages, preserving order."""
    file_ids: list[int] = []
    for msg in messages:
        if not isinstance(msg.content, list):
            continue
        for block in msg.content:
            if not isinstance(block, dict) or block.get("type") != "drive_file":
                continue
            raw_id = block.get("file_id")
            if raw_id is None:
                logger.warning("Skipping drive_file block missing file_id in stream: %s", block)
                continue
            file_ids.append(int(raw_id))
    return file_ids


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


async def _stream_out_of_scope_refusal() -> AsyncGenerator[str, None]:
    """Yield a single SSE done-event carrying the refusal message as content."""
    yield f"data: {json.dumps({'done': True, 'content': REFUSAL_MESSAGE})}\n\n"


def _parse_metadata_list(model_metadata: str | None, key: str) -> list[dict[str, Any]] | None:
    if not model_metadata:
        return None
    try:
        meta = json.loads(model_metadata)
        value = meta.get(key)
        return value if isinstance(value, list) else None
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Failed to parse model_metadata for key %r: %s", key, exc)
        return None


def _extract_query_text(messages: list[ChatMessage]) -> str:
    """Extract the user's plain text from the last user message for RAG retrieval."""
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
    user_id: int,
    query_text: str,
    llm: Any,
) -> list[ChatMessage]:
    """Replace drive_file content blocks with RAG context text blocks.

    Collects all drive_file IDs in each message, calls agentic_retrieve_context once per
    message, groups results by source, and injects one text block per source.
    Returns a new list; original messages are not mutated.
    Base64 and plain text blocks pass through unchanged.

    Raises:
        HTTPException(422): file not found, not owned, or RAG not ready.
        HTTPException(500): agent retrieval or section-chunk fetch failure.
    """
    resolved: list[ChatMessage] = []

    for msg in messages:
        if not isinstance(msg.content, list):
            resolved.append(msg)
            continue

        file_ids: list[int] = []
        non_file_blocks: list[dict[str, Any]] = []
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "drive_file":
                raw_id = block.get("file_id")
                if raw_id is None:
                    logger.warning("Skipping drive_file block missing file_id: %s", block)
                    continue
                file_ids.append(int(raw_id))
            else:
                non_file_blocks.append(block)

        if not file_ids:
            resolved.append(msg)
            continue

        try:
            chunks = await agentic_retrieve_context(query_text, file_ids, user_id, llm)
        except DriveFileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="One or more files not found or not accessible.",
            ) from exc
        except RAGNotReadyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(f"A file is still being processed (status: {exc.rag_status}). Please wait and try again."),
            ) from exc
        except RAGRetrievalError as exc:
            logger.error("RAG retrieval error for file_ids=%s: %s", file_ids, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve document context. Please try again.",
            ) from exc

        grouped = _group_by_source(chunks)
        rag_blocks: list[dict[str, Any]] = [
            {"type": "text", "text": _format_source_block(source, src_chunks)} for source, src_chunks in grouped.items()
        ]

        logger.info(
            "Replaced drive_file blocks file_ids=%s with %d RAG chunks across %d source(s)",
            file_ids,
            len(chunks),
            len(grouped),
        )

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


@chat_router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: ChatService = Depends(get_chat_service),
    llm_service: LLMConfigService = Depends(get_llm_service),
    config: ChatSystemConfig = Depends(get_chat_system_config),
) -> Any:
    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=request.llm_config_id,
        )
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = "No AI Key found for the current user. Please configure an AI key in your chat plugin settings."
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except LLMConfigModelNotSetError as exc:
        logger.warning("LLMConfig %s has no model set: %s", request.llm_config_id, exc)
        detail = "The selected AI key has no model configured. Go to AI Keys to set a model before chatting."
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except LLMConfigInactiveError as exc:
        logger.warning("LLMConfig %s is inactive for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = (
            "The selected AI key is deactivated. Go to AI Keys to "
            "reactivate it, or choose a different one in chat settings."
        )
        await _persist_pre_stream_error(session, service, request, current_user.id, detail)  # type: ignore[arg-type]
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model

    conversation_uuid = request.conversation_id
    query_text = _extract_query_text(request.messages)

    # Pre-flight scope check for brand-new conversations.
    # Runs before any DB writes so an out-of-scope first message leaves no trace.
    _scope_already_checked = False
    if not conversation_uuid:
        _in_scope_preflight = True
        if query_text:
            if not is_query_in_scope(query_text):
                _in_scope_preflight = False
            else:
                preflight_classifier = ScopeClassifier(provider_name=provider_name, api_key=api_key)
                _in_scope_preflight = await preflight_classifier.classify(
                    query_text, history=[], attached_file_names=None
                )
        if not _in_scope_preflight:
            if request.stream:
                return StreamingResponse(
                    _stream_out_of_scope_refusal(),
                    media_type="text/event-stream",
                )
            return ChatCompletionResponse(
                message=ChatMessage(role="assistant", content=REFUSAL_MESSAGE),
                conversation_id=None,
                model=model,
                provider=provider_name,
            )
        _scope_already_checked = True

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
    else:
        conversation = await service.create_conversation(
            session=session,
            user_id=current_user.id,  # type: ignore
            llm_config_id=request.llm_config_id,
            provider=provider_name,
            model=model,
            title=extract_title_from_messages(request.messages, max_length=config.title_max_length),
        )

        first_user_text = get_first_user_text(request.messages)
        if first_user_text:
            title_provider = get_provider(
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                temperature=0.3,
                max_tool_executions=0,
            )
            background_tasks.add_task(
                generate_conversation_title,
                conversation_id=conversation.id,  # type: ignore
                user_id=current_user.id,  # type: ignore
                first_user_message=first_user_text,
                service=service,
                provider=title_provider,
            )

    # Attach any drive files included with the request (covers new-conversation flow
    # where files are selected before the conversation exists in the DB).
    if request.drive_file_ids:
        owned_result = await session.exec(
            select(DriveFileModel.id).where(
                col(DriveFileModel.id).in_(request.drive_file_ids),
                DriveFileModel.user_id == current_user.id,
                DriveFileModel.is_deleted == False,  # noqa: E712
            )
        )
        owned_ids = {file_id for file_id in owned_result.all() if file_id is not None}
        skipped = set(request.drive_file_ids) - owned_ids
        if skipped:
            logger.warning(
                "Skipped %d unowned/deleted drive file IDs for user %s: %s",
                len(skipped),
                current_user.id,
                skipped,
            )
        for file_id in owned_ids:
            await service.attach_drive_file(
                session,
                conversation_id=conversation.id,  # type: ignore
                drive_file_id=file_id,
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

    db_messages = await service.get_conversation_messages(
        session=session,
        conversation_id=conversation.id,  # type: ignore
    )

    try:
        # Fetch conversation attachments early — needed by both the scope classifier
        # (to know files are in play) and the RAG intent router.
        attached_files = await service.list_conversation_attachments(
            session=session,
            conversation_id=conversation.id,  # type: ignore
        )
        attached_file_names = [f.name for f in attached_files]

        # --- Tiered scope check ---
        # Tier 1: fast keyword pre-filter. Tier 2: LLM classifier for nuanced cases.
        _in_scope = True
        if query_text and not _scope_already_checked:
            if not is_query_in_scope(query_text):
                _in_scope = False
            else:
                classifier = ScopeClassifier(provider_name=llm_config.provider, api_key=api_key)
                prior_history: list[HistoryTurn] = [
                    {"role": cast(Literal["user", "assistant"], m.role), "content": m.content}
                    for m in db_messages
                    if m is not db_messages[-1] or not (m.role == "user" and m.content == query_text)
                ]
                _in_scope = await classifier.classify(
                    query_text,
                    history=prior_history,
                    attached_file_names=attached_file_names or None,
                )
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

        # --- RAG Intent Routing: decide whether to retrieve context from attachments ---
        # attached_files already fetched above for the scope check
        should_run_rag = False
        rag_routing_reason: str | None = None
        if attached_files and query_text:
            router = RAGIntentRouter(llm=provider.create_llm())
            decision = await router.decide(
                query=query_text,
                attached_files=attached_files,
                user_id=current_user.id,  # type: ignore[arg-type]
            )
            should_run_rag = decision.should_retrieve
            rag_routing_reason = decision.reason

        # Use DB messages for history, but replace current batch with original
        # request content to preserve content blocks (e.g. base64 file attachments)
        num_current = len(request.messages)
        history: list[dict[str, Any]] = (
            [{"role": m.role, "content": m.content} for m in db_messages[:-num_current]]
            if len(db_messages) > num_current
            else []
        )

        # Synthesize messages based on router decision
        if should_run_rag and attached_files:
            # Synthetic message: drive_file blocks (for RAG resolution) + user's query text
            # so that _extract_query_text finds the question and the user's question is
            # preserved in current after resolution.
            file_blocks: list[dict[str, Any]] = [{"type": "drive_file", "file_id": f.id} for f in attached_files]
            text_block: list[dict[str, Any]] = [{"type": "text", "text": query_text}] if query_text else []
            synthetic_messages = [
                ChatMessage(
                    role="user",
                    content=file_blocks + text_block,
                )
            ]
            unresolved_messages = synthetic_messages
        else:
            unresolved_messages = None

        if request.stream and should_run_rag:
            # Pass synthetic messages as current so the in-stream assembly pass finds the
            # drive_file blocks to replace. The query text block travels with them so the
            # LLM sees both the RAG context and the user's question after replacement.
            current: list[dict[str, Any]] = [{"role": msg.role, "content": msg.content} for msg in unresolved_messages]  # type: ignore[union-attr]
        else:
            # For non-streaming or when RAG is skipped, resolve synchronously
            if should_run_rag and unresolved_messages:
                # _resolve_drive_file_blocks replaces drive_file blocks with RAG context;
                # the query text block is preserved alongside it.
                resolved_messages = await _resolve_drive_file_blocks(
                    messages=unresolved_messages,
                    user_id=current_user.id,  # type: ignore[arg-type]
                    query_text=query_text,
                    llm=provider.create_llm(),
                )
            else:
                # Otherwise use request messages as-is (no RAG)
                resolved_messages = request.messages
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
            if should_run_rag and unresolved_messages:
                stream_kwargs = {
                    "unresolved_messages": unresolved_messages,
                    "user_id": current_user.id,
                    "llm": provider.create_llm(),
                    "should_run_rag": True,
                }
            elif attached_files:
                # Attachments exist but router said skip RAG
                stream_kwargs = {
                    "should_run_rag": False,
                    "rag_routing_reason": rag_routing_reason,
                }
            return StreamingResponse(
                stream_chat_response(
                    provider=provider,
                    messages=messages,
                    conversation=conversation,
                    service=service,
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
    except _PROVIDER_API_ERRORS as e:
        logger.error("Provider API error: %s", e)
        detail = _streaming_error_message(e)
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


async def stream_chat_response(
    provider: BaseChatProvider,
    messages: list[dict[str, Any]],
    conversation: Conversation,
    service: ChatService,
    tools: list[Any] | None = None,
    unresolved_messages: list[ChatMessage] | None = None,
    user_id: int | None = None,
    llm: Any | None = None,
    should_run_rag: bool = False,
    rag_routing_reason: str | None = None,
    _task_holder: list[asyncio.Task[None]] | None = None,
) -> Any:
    # Both Phase 1 (RAG resolution) and Phase 2 (LLM streaming + DB write) run
    # inside an independent asyncio task so that a client disconnect (browser
    # refresh) does not cancel the work. The generator only drains a queue.
    conversation_id: int = conversation.id  # type: ignore[assignment]
    conversation_uuid: str = str(conversation.uuid)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    disconnected = asyncio.Event()

    async def _put(payload: str | None) -> None:
        """Skip enqueue once the consumer has disconnected to prevent unbounded accumulation."""
        if not disconnected.is_set():
            await queue.put(payload)

    async def _process_and_stream() -> None:
        async with session_scope() as bg_session:
            try:
                await _run(bg_session)
            except BaseException as exc:
                # Intentionally broad: this is the top-level boundary of a fire-and-forget
                # asyncio task. Anything that escapes _run must still deliver an error payload
                # so the SSE consumer doesn't block forever on queue.get(). CancelledError is
                # a BaseException (not Exception), so we re-raise it after the sentinel to
                # preserve asyncio's cooperative cancellation contract.
                logger.exception("Unhandled error in stream task for conversation %s", conversation_id)
                error_text = "An unexpected error occurred. Please try again."
                await service.add_message(
                    session=bg_session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=error_text,
                    is_error=True,
                )
                await _put(json.dumps({"error": error_text, "done": True}))
                if not isinstance(exc, Exception):
                    raise
            finally:
                await _put(None)

    async def _run(bg_session: AsyncSession) -> None:
        confirmed_rag_sections: list[dict[str, str | None]] = []

        # --- Phase 1: RAG resolution ---
        file_ids: list[int] = _collect_drive_file_ids(unresolved_messages) if unresolved_messages else []

        if should_run_rag and unresolved_messages and user_id is not None:
            await _put(json.dumps({"status": "scanning_attachments", "file_count": len(file_ids), "done": False}))

        if not should_run_rag and rag_routing_reason is not None:
            await _put(json.dumps({"status": "skipping_rag", "reason": rag_routing_reason, "done": False}))

        if should_run_rag and unresolved_messages and user_id is not None:
            query_text = _extract_query_text(unresolved_messages)
            any_results_found = False

            await _put(json.dumps({"status": "searching_documents", "file_count": len(file_ids), "done": False}))

            logger.info("Agentic RAG search for file_ids=%s query_len=%d", file_ids, len(query_text))
            assert llm is not None, "llm must be provided when RAG resolution is active"
            try:
                all_chunks = await agentic_retrieve_context(query_text, file_ids, user_id, llm)
            except DriveFileNotFoundError as exc:
                logger.error("Agentic RAG failed for file_ids=%s: %s", file_ids, exc)
                error_text = "The attached file could not be found or is no longer accessible."
                await service.add_message(
                    session=bg_session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=error_text,
                    is_error=True,
                )
                await _put(json.dumps({"error": error_text, "done": True}))
                return
            except RAGNotReadyError as exc:
                logger.error("Agentic RAG failed for file_ids=%s: %s", file_ids, exc)
                error_text = "The attached file is still being processed. Please wait a moment and try again."
                await service.add_message(
                    session=bg_session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=error_text,
                    is_error=True,
                )
                await _put(json.dumps({"error": error_text, "done": True}))
                return
            except RAGRetrievalError as exc:
                logger.error("Agentic RAG failed for file_ids=%s: %s", file_ids, exc)
                error_text = "Failed to search the attached file. Please try again."
                await service.add_message(
                    session=bg_session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=error_text,
                    is_error=True,
                )
                await _put(json.dumps({"error": error_text, "done": True}))
                return

            grouped = _group_by_source(all_chunks)
            source_blocks: dict[str, str] = {
                source: _format_source_block(source, src_chunks) for source, src_chunks in grouped.items()
            }
            any_results_found = bool(source_blocks)

            # Build confirmed_rag_sections from each chunk's hierarchy
            seen_section_keys: set[str] = set()
            for chunk in all_chunks:
                label = "subsection" if chunk.subsection else "section" if chunk.section else "chapter"
                parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
                name = " / ".join(parts) if parts else "General"
                key = f"{label}:{name}:{chunk.source_name}"
                if key not in seen_section_keys:
                    seen_section_keys.add(key)
                    confirmed_rag_sections.append({"type": label, "name": name, "source": chunk.source_name})

            # Single assembly pass: replace all drive_file blocks with resolved RAG context.
            rag_block_list: list[dict[str, Any]] = [{"type": "text", "text": text} for text in source_blocks.values()]
            for m in messages:
                if not isinstance(m.get("content"), list):
                    continue
                user_text_blocks: list[dict[str, Any]] = []
                other_blocks: list[dict[str, Any]] = []
                has_drive_file = False
                for b in m["content"]:
                    if isinstance(b, dict) and b.get("type") == "drive_file":
                        has_drive_file = True
                    elif isinstance(b, dict) and b.get("type") == "text":
                        user_text_blocks.append(b)
                    else:
                        other_blocks.append(b)
                if not has_drive_file:
                    continue
                if rag_block_list:
                    m["content"] = (
                        [{"type": "text", "text": _RAG_CONTEXT_PROMPT}]
                        + other_blocks
                        + rag_block_list
                        + user_text_blocks
                    )
                else:
                    m["content"] = other_blocks + user_text_blocks

            if not any_results_found:
                no_chunks_msg = (
                    "I searched your documents but couldn't find content closely "
                    "matching your query.\n\n"
                    "Please try rephrasing your question, or check that your documents "
                    "contain information about this topic."
                )
                await service.add_message(
                    session=bg_session,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=no_chunks_msg,
                    message_type="text",
                )
                await _put(json.dumps({"done": True, "content": no_chunks_msg, "conversation_id": conversation_uuid}))
                return

            for section in confirmed_rag_sections:
                await _put(json.dumps({"status": "section_scanning", "section": section, "done": False}))
            for section in confirmed_rag_sections:
                await _put(json.dumps({"status": "section_confirmed", "section": section, "done": False}))
            await _put(json.dumps({"status": "generating", "done": False}))

        # Safety strip: remove unresolved drive_file blocks before hitting the LLM.
        for m in messages:
            if isinstance(m.get("content"), list):
                m["content"] = [b for b in m["content"] if not (isinstance(b, dict) and b.get("type") == "drive_file")]

        # --- Phase 2: LLM streaming ---
        full_response = ""
        completed_tool_calls: list[dict[str, Any]] = []
        try:
            async for event in provider.stream_message(messages, tools=tools):
                if event["type"] == "token":
                    token = event["content"]
                    full_response += token
                    await _put(json.dumps({"token": token, "done": False}))
                elif event["type"] == "tool_start":
                    await _put(
                        json.dumps(
                            {
                                "status": "tool_call",
                                "tool_name": event["name"],
                                "tool_status": "running",
                                "done": False,
                            }
                        )
                    )
                elif event["type"] == "tool_end":
                    completed_tool_calls.append({"name": event["name"]})
                    await _put(
                        json.dumps(
                            {
                                "status": "tool_call",
                                "tool_name": event["name"],
                                "tool_status": "done",
                                "done": False,
                            }
                        )
                    )

            metadata: dict[str, Any] = {}
            if confirmed_rag_sections:
                metadata["rag_sections"] = confirmed_rag_sections
            if completed_tool_calls:
                metadata["tool_calls"] = completed_tool_calls

            assistant_message = await service.add_message(
                session=bg_session,
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                metadata=metadata if metadata else None,
            )
            await _put(
                json.dumps(
                    {
                        "token": "",
                        "done": True,
                        "conversation_id": conversation_uuid,
                        "message": {
                            "id": assistant_message.id,
                            "role": "assistant",
                            "content": full_response,
                            "message_type": "text",
                            "attachment_name": None,
                            "attachment_size": None,
                            "rag_sections": confirmed_rag_sections or None,
                            "tool_calls": completed_tool_calls or None,
                        },
                    }
                )
            )

        except _PROVIDER_API_ERRORS as e:
            user_message = _streaming_error_message(e)
            logger.error("Streaming failed: %s", e)
            await service.add_message(
                session=bg_session,
                conversation_id=conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            await _put(json.dumps({"error": user_message, "done": True}))

        except (OSError, LangChainException) as e:
            logger.exception("Unexpected streaming error: %s", e)
            user_message = "An error occurred while generating a response. Please try again."
            await service.add_message(
                session=bg_session,
                conversation_id=conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            await _put(json.dumps({"error": user_message, "done": True}))

    task = asyncio.create_task(_process_and_stream())
    if _task_holder is not None:
        _task_holder.append(task)

    try:
        while True:
            payload = await queue.get()
            if payload is None:
                break
            yield f"data: {payload}\n\n"
    except asyncio.CancelledError:
        disconnected.set()
        raise


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
                rag_sections=_parse_metadata_list(msg.model_metadata, "rag_sections"),
                tool_calls=_parse_metadata_list(msg.model_metadata, "tool_calls"),
                is_error=msg.is_error,
            )
            for msg in messages
        ],
    )


@chat_router.get(
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
        user_id=current_user.id,  # type: ignore
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = await service.get_last_conversation_message(
        session=session,
        conversation_id=conversation.id,  # type: ignore
    )
    if msg is None:
        return None

    return MessageResponse(
        id=msg.id,  # type: ignore
        role=msg.role,
        content=msg.content,
        tokens_used=msg.tokens_used,
        cost=msg.cost,
        created_at=msg.created_at,
        message_type=msg.message_type,
        attachment_name=msg.attachment_name,
        attachment_size=msg.attachment_size,
        rag_sections=_parse_metadata_list(msg.model_metadata, "rag_sections"),
        tool_calls=_parse_metadata_list(msg.model_metadata, "tool_calls"),
        is_error=msg.is_error,
    )


@chat_router.get(
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


@chat_router.post(
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
    df_result = await session.exec(
        select(DriveFileModel).where(
            DriveFileModel.id == body.drive_file_id,
            DriveFileModel.user_id == current_user.id,
            DriveFileModel.is_deleted == False,  # noqa: E712
        )
    )
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


@chat_router.delete(
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

    df_result = await session.exec(
        select(DriveFileModel).where(
            DriveFileModel.id == drive_file_id,
            DriveFileModel.user_id == current_user.id,
            DriveFileModel.is_deleted == False,  # noqa: E712
        )
    )
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


def get_parameters_schema(args_schema: type[BaseModel] | dict[str, Any] | None) -> dict[str, Any]:
    if args_schema is None:
        return {}
    if isinstance(args_schema, dict):
        return args_schema
    return args_schema.model_json_schema()


@chat_router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    _current_user: User = Depends(get_current_user),
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
