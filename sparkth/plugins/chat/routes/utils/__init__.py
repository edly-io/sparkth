import json
from typing import Any

from fastapi import HTTPException, status

from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
    format_document_chunks_as_llm_context,
)
from sparkth.plugins.chat.constants import RAG_CONTEXT_PROMPT
from sparkth.plugins.chat.messages import extract_query_text
from sparkth.plugins.chat.schemas import ChatCompletionRequest, ChatMessage
from sparkth.plugins.chat.tools import ToolRegistry

logger = get_logger(__name__)


async def resolve_document_blocks(
    messages: list[ChatMessage],
    llm: Any,
) -> list[ChatMessage]:
    """Replace document attachment content blocks with RAG context text blocks.

    Collects all Document IDs in each message, calls agentic_retrieve_context
    once per message, groups results by source, and injects one text block per source.
    Returns a new list; original messages are not mutated.
    Base64 and plain text blocks pass through unchanged.

    Raises:
        HTTPException(422): document not found or RAG not ready.
        HTTPException(500): agent retrieval or section-chunk fetch failure.
    """
    query_text = extract_query_text(messages)
    resolved: list[ChatMessage] = []

    for msg in messages:
        if not isinstance(msg.content, list):
            resolved.append(msg)
            continue

        document_ids: list[int] = []
        non_document_blocks: list[dict[str, Any]] = []
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "drive_file":
                raw_id = block.get("file_id")
                if raw_id is None:
                    logger.warning("Skipping document attachment block missing file_id: %s", block)
                    continue
                document_ids.append(int(raw_id))
            else:
                non_document_blocks.append(block)

        if not document_ids:
            resolved.append(msg)
            continue

        chunks = await _retrieve_rag_chunks(document_ids, query_text, llm)

        rag_blocks: list[dict[str, Any]] = (
            [{"type": "text", "text": format_document_chunks_as_llm_context(chunks)}] if chunks else []
        )
        logger.info(
            "Replaced legacy document attachment blocks document_ids=%s with %d RAG chunks across %d source(s)",
            document_ids,
            len(chunks),
            len({chunk.source_name for chunk in chunks}),
        )

        if rag_blocks:
            user_text_blocks = [b for b in non_document_blocks if isinstance(b, dict) and b.get("type") == "text"]
            other_blocks = [b for b in non_document_blocks if not (isinstance(b, dict) and b.get("type") == "text")]
            new_blocks: list[dict[str, Any]] = (
                [{"type": "text", "text": RAG_CONTEXT_PROMPT}] + other_blocks + rag_blocks + user_text_blocks
            )
        else:
            new_blocks = non_document_blocks
        resolved.append(ChatMessage(role=msg.role, content=new_blocks, attachment=msg.attachment))

    return resolved


async def _retrieve_rag_chunks(
    document_ids: list[int],
    query_text: str,
    llm: Any,
) -> list[RetrievedChunk]:
    """Retrieve RAG chunks for Document IDs.

    Document existence and readiness are validated inside agentic_retrieve_context.
    Raises HTTPException if documents are missing, not ready, or retrieval fails.
    """
    try:
        return await agentic_retrieve_context(query_text, document_ids, llm)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_("One or more documents not found or not accessible."),
        ) from exc
    except RAGNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_("A document is still being processed (status: {status}). Please wait and try again.").format(
                status=exc.status
            ),
        ) from exc
    except RAGRetrievalError as exc:
        logger.error("RAG retrieval error for document_ids=%s: %s", document_ids, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_("Failed to retrieve document context. Please try again."),
        ) from exc


async def resolve_tools(
    request: ChatCompletionRequest,
    tool_registry: ToolRegistry,
) -> list[Any] | None:
    """Resolve the tool list from the request's tools field."""
    if request.tools == "none" or request.tools == []:
        logger.info("Tools explicitly disabled")
        return None
    if request.tools == "*" or request.tools == "all":
        tools = tool_registry.get_all_tools()
        logger.info("Auto-including all %d available tools (default)", len(tools))
        return tools
    if request.tools and isinstance(request.tools, list):
        tools = tool_registry.get_tools_by_names(request.tools)
        if not tools:
            logger.warning("No tools found for: %s", request.tools)
        return tools
    return None


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
