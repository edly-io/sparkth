import json
from typing import Any, AsyncGenerator, cast
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.config import ChatSettings
from app.core_plugins.chat.constants import RAG_CONTEXT_PROMPT
from app.core_plugins.chat.conversation_title import (
    extract_title_from_messages,
    generate_conversation_title,
    get_first_user_text,
)
from app.core_plugins.chat.intent_router import RAGIntentRouter
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.schemas import ChatCompletionRequest, ChatMessage
from app.core_plugins.chat.service import ChatService
from app.core_plugins.chat.tools import ToolRegistry
from app.lib.log import get_logger
from app.lib.rag import (
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
)
from app.llm.classifier import HistoryTurn, ScopeClassifier
from app.llm.prompt import REFUSAL_MESSAGE, is_query_in_scope
from app.llm.providers import BaseChatProvider, get_provider
from app.models.drive import DriveFile as DriveFileModel

logger = get_logger(__name__)


async def stream_out_of_scope_refusal() -> AsyncGenerator[str, None]:
    """Yield a single SSE done-event carrying the refusal message as content."""
    yield f"data: {json.dumps({'done': True, 'content': REFUSAL_MESSAGE})}\n\n"


def extract_query_text(messages: list[ChatMessage]) -> str:
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


def _format_source_block(source_name: str, chunks: list[RetrievedChunk]) -> str:
    lines = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        label = " / ".join(parts) if parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")
    return "\n".join(lines)


def _group_by_source(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.source_name, []).append(chunk)
    return grouped


async def resolve_drive_file_blocks(
    messages: list[ChatMessage],
    user_id: int,
    llm: Any,
) -> list[ChatMessage]:
    """Replace drive_file content blocks with RAG context text blocks.

    Returns a new list; original messages are not mutated.
    Base64 and plain text blocks pass through unchanged.

    Raises:
        HTTPException(422): file not found, not owned, or RAG not ready.
        HTTPException(500): agent retrieval or section-chunk fetch failure.
    """
    query_text = extract_query_text(messages)
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
        file_ids: list[int] = []
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
                [{"type": "text", "text": RAG_CONTEXT_PROMPT}] + other_blocks + rag_blocks + user_text_blocks
            )
        else:
            new_blocks = non_file_blocks
        resolved.append(ChatMessage(role=msg.role, content=new_blocks, attachment=msg.attachment))

    return resolved


async def persist_pre_stream_error(
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


async def get_or_create_conversation(
    *,
    session: AsyncSession,
    service: ChatService,
    conversation_uuid: UUID | None,
    user_id: int,
    messages: list[ChatMessage],
    llm_config_id: int,
    provider_name: str,
    api_key: str,
    model: str,
    config: ChatSettings,
    background_tasks: BackgroundTasks,
) -> Conversation:
    """Resolve an existing conversation by UUID, or create a new one and schedule title generation."""
    if conversation_uuid:
        conversation = await service.get_conversation_by_uuid(
            session=session,
            uuid=conversation_uuid,
            user_id=user_id,
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {conversation_uuid} not found",
            )
        return conversation

    conversation = await service.create_conversation(
        session=session,
        user_id=user_id,
        llm_config_id=llm_config_id,
        provider=provider_name,
        model=model,
        title=extract_title_from_messages(messages, max_length=config.title_max_length),
    )
    first_user_text = get_first_user_text(messages)
    if first_user_text:
        title_provider = get_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            temperature=config.title_llm_temperature,
            max_tool_executions=0,
        )
        background_tasks.add_task(
            generate_conversation_title,
            conversation_id=cast(int, conversation.id),
            user_id=user_id,
            first_user_message=first_user_text,
            service=service,
            provider=title_provider,
        )
    return conversation


async def attach_request_drive_files(
    session: AsyncSession,
    service: ChatService,
    drive_file_ids: list[int],
    user_id: int,
    conversation_id: int,
) -> None:
    """Attach owned drive files to the conversation, silently skipping any unowned IDs."""
    owned_result = await session.exec(
        select(DriveFileModel.id).where(
            col(DriveFileModel.id).in_(drive_file_ids),
            DriveFileModel.user_id == user_id,
            DriveFileModel.is_deleted == False,  # noqa: E712
        )
    )
    owned_ids = {file_id for file_id in owned_result.all() if file_id is not None}
    skipped = set(drive_file_ids) - owned_ids
    if skipped:
        logger.warning(
            "Skipped %d unowned/deleted drive file IDs for user %s: %s",
            len(skipped),
            user_id,
            skipped,
        )
    for file_id in owned_ids:
        await service.attach_drive_file(session, conversation_id=conversation_id, drive_file_id=file_id)


async def persist_incoming_messages(
    session: AsyncSession,
    service: ChatService,
    messages: list[ChatMessage],
    conversation_id: int,
) -> None:
    """Persist the request's incoming messages to the conversation."""
    for msg in messages:
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
            conversation_id=conversation_id,
            role=msg.role,
            content=stored_content,
            message_type="attachment" if msg.attachment else "text",
            attachment_name=msg.attachment.name if msg.attachment else None,
            attachment_size=msg.attachment.size if msg.attachment else None,
        )


async def classify_in_scope(
    query_text: str,
    provider_name: str,
    api_key: str,
    history: list[HistoryTurn],
    attached_file_names: list[str] | None,
) -> bool:
    """Tiered scope check: fast keyword pre-filter, then LLM classifier. Empty query is always in scope."""
    if not query_text:
        return True
    if not is_query_in_scope(query_text):
        return False
    classifier = ScopeClassifier(provider_name=provider_name, api_key=api_key)
    return await classifier.classify(query_text, history=history, attached_file_names=attached_file_names)


async def resolve_tools(
    request: ChatCompletionRequest,
    tool_registry: ToolRegistry,
) -> list[Any] | None:
    """Resolve the tool list from the request's tools field."""
    if request.tools == "none" or request.tools == []:
        logger.info("Tools explicitly disabled")
        return None
    if request.tools == "*" or request.tools == "all":
        tools = await tool_registry.get_all_tools()
        logger.info("Auto-including all %d available tools (default)", len(tools))
        return tools
    if request.tools and isinstance(request.tools, list):
        tools = await tool_registry.get_tools_by_names(request.tools)
        if not tools:
            logger.warning("No tools found for: %s", request.tools)
        return tools
    return None


async def resolve_rag_intent(
    attached_files: list[DriveFileModel],
    query_text: str,
    user_id: int,
    provider: BaseChatProvider,
) -> tuple[bool, str | None]:
    """Decide whether to run RAG retrieval for the current request.

    Returns (should_run_rag, routing_reason). Always False when there are no
    attached files or no query text.
    """
    if not attached_files or not query_text:
        return False, None
    rag_router = RAGIntentRouter(llm=provider.create_llm())
    decision = await rag_router.decide(
        query=query_text,
        attached_files=attached_files,
        user_id=user_id,
    )
    return decision.should_retrieve, decision.reason


def parse_metadata_list(model_metadata: str | None, key: str) -> list[dict[str, Any]] | None:
    """Extract a list value from a JSON-serialised metadata string."""
    if not model_metadata:
        return None
    try:
        meta = json.loads(model_metadata)
        value = meta.get(key)
        return value if isinstance(value, list) else None
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.error("Failed to parse model_metadata for key %r: %s", key, exc)
        return None
