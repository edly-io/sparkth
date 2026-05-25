import asyncio
import json
from typing import Any, AsyncGenerator, Literal, cast

import anthropic
import httpx
import openai
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.api_core import exceptions as google_exceptions
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.constants import DEFAULT_SIMILARITY_THRESHOLD, TITLE_LLM_TEMPERATURE
from app.core_plugins.chat.conversation_title import ConversationTitleGenerator
from app.core_plugins.chat.intent_router import RAGIntentRouter, RAGIntentRouterError
from app.core_plugins.chat.lms_credentials import LMSCredentialsBuilder
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.routes.dependencies import get_chat_service, get_chat_system_config, get_rag_context_service
from app.core_plugins.chat.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage
from app.core_plugins.chat.service import ChatService
from app.core_plugins.chat.tools import get_tool_registry
from app.lib.db import get_async_session, session_scope
from app.lib.log import get_logger
from app.llm.classifier import HistoryTurn, ScopeClassifier
from app.llm.exceptions import LLMConfigInactiveError, LLMConfigModelNotSetError, LLMConfigNotFoundError
from app.llm.prompt import REFUSAL_MESSAGE, is_query_in_scope
from app.llm.providers import BaseChatProvider, get_provider
from app.llm.service import LLMConfigService, get_llm_service
from app.models.drive import DriveFile as DriveFileModel
from app.models.user import User
from app.rag.context_service import RAGContextService
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.types import RAGContext
from app.rag.utils import get_asset

logger = get_logger(__name__)

_RAG_CONTEXT_PROMPT = get_asset("rag_context_replacement_prompt", "txt")
if not isinstance(_RAG_CONTEXT_PROMPT, str):
    raise TypeError("rag_context_replacement_prompt asset must be a string")

router = APIRouter()

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


async def _stream_out_of_scope_refusal() -> AsyncGenerator[str, None]:
    """Yield a single SSE done-event carrying the refusal message as content."""
    yield f"data: {json.dumps({'done': True, 'content': REFUSAL_MESSAGE})}\n\n"


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
        HTTPException(500): agent retrieval or section-chunk fetch failure.
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


@router.post("/completions", response_model=ChatCompletionResponse)
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
            title=ConversationTitleGenerator.extract_title_from_messages(
                request.messages, max_length=config.title_max_length
            ),
        )

        first_user_text = ConversationTitleGenerator.get_first_user_text(request.messages)
        if first_user_text:
            title_provider = get_provider(
                provider_name=provider_name,
                api_key=api_key,
                model=model,
                temperature=TITLE_LLM_TEMPERATURE,
                max_tool_executions=0,
            )
            background_tasks.add_task(
                ConversationTitleGenerator.generate,
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
            rag_router = RAGIntentRouter(llm=provider.create_llm())
            decision = await rag_router.decide(
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
                    session=session,
                    user_id=current_user.id,  # type: ignore[arg-type]
                    rag_service=rag_service,
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
        lms_credentials_message = await LMSCredentialsBuilder.build_message(
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
                    "rag_service": rag_service,
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
    rag_service: RAGContextService | None = None,
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
        if should_run_rag and unresolved_messages and rag_service and user_id is not None:
            file_count = sum(
                1
                for msg in unresolved_messages
                if isinstance(msg.content, list)
                for b in msg.content
                if isinstance(b, dict) and b.get("type") == "drive_file"
            )
            await _put(json.dumps({"status": "scanning_attachments", "file_count": file_count, "done": False}))

        if not should_run_rag and rag_routing_reason is not None:
            await _put(json.dumps({"status": "skipping_rag", "reason": rag_routing_reason, "done": False}))

        if unresolved_messages and rag_service and user_id is not None:
            query_text = _extract_query_text(unresolved_messages)
            files_with_no_results: list[str] = []
            any_results_found = False
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

                    await _put(json.dumps({"status": "searching_document", "file_id": file_id, "done": False}))

                    logger.info("Agentic RAG search for file_id=%d query_len=%d", file_id, len(query_text))
                    try:
                        context = await rag_service.get_context_via_agent(
                            session=bg_session,
                            user_id=user_id,
                            file_db_id=file_id,
                            query=query_text,
                            llm=llm,
                        )
                    except DriveFileNotFoundError as exc:
                        logger.error("Agentic RAG failed for file_id=%d: %s", file_id, exc)
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
                        logger.error("Agentic RAG failed for file_id=%d: %s", file_id, exc)
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
                        logger.error("Agentic RAG failed for file_id=%d: %s", file_id, exc)
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

                    source_name = context.source_name
                    results = context.chunks

                    if not results:
                        files_with_no_results.append(source_name)
                        continue

                    any_results_found = True
                    rag_context_map[file_id] = context

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

            # Single assembly pass: replace all drive_file blocks with resolved RAG context.
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

            if files_with_no_results and not any_results_found:
                source_label = (
                    f"**{files_with_no_results[0]}**" if len(files_with_no_results) == 1 else "your documents"
                )
                no_chunks_msg = (
                    f"I searched {source_label} but couldn't find content closely "
                    f"matching your query.\n\n"
                    f"Please try rephrasing your question, or check that your documents "
                    f"contain information about this topic."
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
