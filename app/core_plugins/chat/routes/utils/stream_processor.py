import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, cast

import anthropic
import httpx
import openai
from google.api_core import exceptions as google_exceptions
from langchain_core.exceptions import LangChainException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.constants import LLM_PROVIDER_API_ERRORS, RAG_CONTEXT_PROMPT
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.routes.utils import (
    collect_document_ids,
    extract_query_text,
)
from app.core_plugins.chat.schemas import ChatMessage
from app.core_plugins.chat.service import ChatService
from app.lib.db import session_scope
from app.lib.llm import BaseChatProvider
from app.lib.log import get_logger
from app.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
    format_document_chunks_as_llm_context,
)

logger = get_logger(__name__)


def streaming_error_message(exc: Exception) -> str:
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


def rag_retrieval_error_message(exc: Exception) -> str:
    """Map RAG retrieval exceptions to concise, user-facing error messages."""
    if isinstance(exc, DocumentNotFoundError):
        return "The attached document could not be found or is no longer accessible."
    if isinstance(exc, RAGNotReadyError):
        return "The attached document is still being processed. Please wait a moment and try again."
    return "Failed to search the attached document. Please try again."


class ChatStreamProcessor:
    """Holds all shared state for a single streaming chat response.

    Processing runs inside a background asyncio task so a client disconnect
    does not interrupt the DB write; the generator side only drains a queue.
    """

    def __init__(
        self,
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
    ) -> None:
        self.provider = provider
        self.messages = messages
        self.service = service
        self.tools = tools
        self.unresolved_messages = unresolved_messages
        self.user_id = user_id
        self.llm = llm
        self.should_run_rag = should_run_rag
        self.rag_routing_reason = rag_routing_reason
        self.conversation_id: int = cast(int, conversation.id)
        self.conversation_uuid: str = str(conversation.uuid)
        self.queue: asyncio.Queue[str | None] = asyncio.Queue()
        self.disconnected: asyncio.Event = asyncio.Event()

    def _build_rag_context(self, all_chunks: list[RetrievedChunk]) -> tuple[str, list[dict[str, str | None]]]:
        """Section deduplication prevents the same section appearing twice in the
        UI when multiple chunks come from the same chapter/section/subsection.
        """
        rag_context = format_document_chunks_as_llm_context(all_chunks)
        seen_section_keys: set[str] = set()
        confirmed_rag_sections: list[dict[str, str | None]] = []
        for chunk in all_chunks:
            label = "subsection" if chunk.subsection else "section" if chunk.section else "chapter"
            parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
            name = " / ".join(parts) if parts else "General"
            key = f"{label}:{name}:{chunk.source_name}"
            if key not in seen_section_keys:
                seen_section_keys.add(key)
                confirmed_rag_sections.append({"type": label, "name": name, "source": chunk.source_name})
        return rag_context, confirmed_rag_sections

    def _inject_rag_into_messages(self, rag_context: str) -> None:
        """Mutates self.messages in-place to avoid copying large message lists."""
        rag_block_list: list[dict[str, Any]] = [{"type": "text", "text": rag_context}] if rag_context else []
        for m in self.messages:
            if not isinstance(m.get("content"), list):
                continue
            user_text_blocks: list[dict[str, Any]] = []
            other_blocks: list[dict[str, Any]] = []
            has_document_block = False
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "drive_file":
                    has_document_block = True
                elif isinstance(b, dict) and b.get("type") == "text":
                    user_text_blocks.append(b)
                else:
                    other_blocks.append(b)
            if not has_document_block:
                continue
            if rag_block_list:
                m["content"] = (
                    [{"type": "text", "text": RAG_CONTEXT_PROMPT}] + other_blocks + rag_block_list + user_text_blocks
                )
            else:
                m["content"] = other_blocks + user_text_blocks

    def _strip_unresolved_document_blocks(self) -> None:
        """Ensures the LLM never receives raw file-reference blocks that RAG did not resolve."""
        for m in self.messages:
            if isinstance(m.get("content"), list):
                m["content"] = [b for b in m["content"] if not (isinstance(b, dict) and b.get("type") == "drive_file")]

    async def _put(self, payload: str | None) -> None:
        """Skips enqueue once the consumer disconnects to avoid unbounded queue accumulation."""
        if not self.disconnected.is_set():
            await self.queue.put(payload)

    async def _emit(self, payload: dict[str, Any]) -> None:
        """Serialise an SSE payload onto the queue; every status/token/error event flows through here."""
        await self._put(json.dumps(payload))

    async def _persist_and_emit_error(self, error_text: str, bg_session: AsyncSession) -> None:
        """Persists the error to DB before emitting the SSE so the failure is saved even if the client has dropped."""
        await self.service.add_message(
            session=bg_session,
            conversation_id=self.conversation_id,
            role="assistant",
            content=error_text,
            is_error=True,
        )
        await self._emit({"error": error_text, "done": True})

    async def _retrieve_rag_chunks(
        self,
        query_text: str,
        document_ids: list[int],
        bg_session: AsyncSession,
    ) -> list[RetrievedChunk] | None:
        """Returns None when retrieval fails; the error SSE and DB write are already handled before returning."""
        await self._emit({"status": "searching_documents", "file_count": len(document_ids), "done": False})
        logger.info("Agentic RAG search for document_ids=%s query_len=%d", document_ids, len(query_text))
        if self.llm is None:
            raise AssertionError("llm must be provided when RAG resolution is active")
        try:
            return await agentic_retrieve_context(query_text, document_ids, self.llm)
        except (DocumentNotFoundError, RAGNotReadyError, RAGRetrievalError) as exc:
            logger.error("Agentic RAG failed for document_ids=%s: %s", document_ids, exc)
            await self._persist_and_emit_error(rag_retrieval_error_message(exc), bg_session)
            return None

    async def _emit_no_rag_results_response(self, bg_session: AsyncSession) -> None:
        """Persists the message to DB before emitting SSE so it is saved even if the connection drops."""
        no_chunks_msg = (
            "I searched your documents but couldn't find content closely "
            "matching your query.\n\n"
            "Please try rephrasing your question, or check that your documents "
            "contain information about this topic."
        )
        await self.service.add_message(
            session=bg_session,
            conversation_id=self.conversation_id,
            role="assistant",
            content=no_chunks_msg,
            message_type="text",
        )
        await self._emit({"done": True, "content": no_chunks_msg, "conversation_id": self.conversation_uuid})

    async def _emit_rag_section_events(self, confirmed_rag_sections: list[dict[str, str | None]]) -> None:
        """Two-pass emit (scanning then confirmed) lets the UI animate each section
        before marking it resolved, rather than all sections appearing at once.
        """
        for section in confirmed_rag_sections:
            await self._emit({"status": "section_scanning", "section": section, "done": False})
        for section in confirmed_rag_sections:
            await self._emit({"status": "section_confirmed", "section": section, "done": False})
        await self._emit({"status": "generating", "done": False})

    async def _run_rag_phase(self, bg_session: AsyncSession) -> list[dict[str, str | None]] | None:
        """Return value convention: None means the response is already complete (error or no-results handled);
        [] means RAG was skipped but the LLM phase should still run.
        """
        if not self.should_run_rag or not self.unresolved_messages or self.user_id is None:
            if self.rag_routing_reason is not None:
                await self._emit({"status": "skipping_rag", "reason": self.rag_routing_reason, "done": False})
            return []

        document_ids = collect_document_ids(self.unresolved_messages)
        await self._emit({"status": "scanning_attachments", "file_count": len(document_ids), "done": False})

        query_text = extract_query_text(self.unresolved_messages)
        chunks = await self._retrieve_rag_chunks(query_text, document_ids, bg_session)
        if chunks is None:
            return None

        rag_context, confirmed_rag_sections = self._build_rag_context(chunks)
        if not rag_context:
            await self._emit_no_rag_results_response(bg_session)
            return None

        self._inject_rag_into_messages(rag_context)
        await self._emit_rag_section_events(confirmed_rag_sections)
        return confirmed_rag_sections

    async def _collect_stream_response(self, bg_session: AsyncSession) -> tuple[str, list[dict[str, Any]]] | None:
        """Returns None when a streaming error is handled; the error SSE and DB write are already done."""
        full_response = ""
        completed_tool_calls: list[dict[str, Any]] = []
        try:
            async for event in self.provider.stream_message(self.messages, tools=self.tools):
                if event["type"] == "token":
                    token = event["content"]
                    full_response += token
                    await self._emit({"token": token, "done": False})
                elif event["type"] == "tool_start":
                    await self._emit(
                        {"status": "tool_call", "tool_name": event["name"], "tool_status": "running", "done": False}
                    )
                elif event["type"] == "tool_end":
                    completed_tool_calls.append({"name": event["name"]})
                    await self._emit(
                        {"status": "tool_call", "tool_name": event["name"], "tool_status": "done", "done": False}
                    )
            return full_response, completed_tool_calls
        except LLM_PROVIDER_API_ERRORS as e:
            logger.error("Streaming failed: %s", e)
            await self._persist_and_emit_error(streaming_error_message(e), bg_session)
            return None
        except (OSError, LangChainException) as e:
            logger.exception("Unexpected streaming error: %s", e)
            await self._persist_and_emit_error(
                "An error occurred while generating a response. Please try again.", bg_session
            )
            return None

    async def _persist_and_emit_done(
        self,
        full_response: str,
        confirmed_rag_sections: list[dict[str, str | None]],
        completed_tool_calls: list[dict[str, Any]],
        bg_session: AsyncSession,
    ) -> None:
        """The done SSE payload includes the full message object so the client can
        update its state without a separate fetch after the stream closes.
        """
        metadata: dict[str, Any] = {}
        if confirmed_rag_sections:
            metadata["rag_sections"] = confirmed_rag_sections
        if completed_tool_calls:
            metadata["tool_calls"] = completed_tool_calls
        assistant_message = await self.service.add_message(
            session=bg_session,
            conversation_id=self.conversation_id,
            role="assistant",
            content=full_response,
            metadata=metadata if metadata else None,
        )
        await self._emit(
            {
                "token": "",
                "done": True,
                "conversation_id": self.conversation_uuid,
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

    async def _run_llm_phase(
        self,
        confirmed_rag_sections: list[dict[str, str | None]],
        bg_session: AsyncSession,
    ) -> None:
        result = await self._collect_stream_response(bg_session)
        if result is None:
            return
        full_response, completed_tool_calls = result
        await self._persist_and_emit_done(full_response, confirmed_rag_sections, completed_tool_calls, bg_session)

    async def _run(self, bg_session: AsyncSession) -> None:
        confirmed_rag_sections = await self._run_rag_phase(bg_session)
        if confirmed_rag_sections is None:
            return
        self._strip_unresolved_document_blocks()
        await self._run_llm_phase(confirmed_rag_sections, bg_session)

    async def _process_and_stream(self) -> None:
        """BaseException (not Exception) is caught so the None sentinel always reaches
        the generator even on KeyboardInterrupt or SystemExit, while non-Exception
        subclasses are still re-raised after cleanup.
        """
        async with session_scope() as bg_session:
            try:
                await self._run(bg_session)
            except BaseException as exc:
                logger.exception("Unhandled error in stream task for conversation %s", self.conversation_id)
                await self._persist_and_emit_error("An unexpected error occurred. Please try again.", bg_session)
                if not isinstance(exc, Exception):
                    raise
            finally:
                await self._put(None)

    async def stream(self, _task_holder: list[asyncio.Task[None]] | None = None) -> AsyncGenerator[str, None]:
        """Processing runs in a separate task so a client disconnect (CancelledError on the generator)
        does not cancel the DB write mid-flight. _task_holder lets the caller hold a reference
        to prevent the task from being garbage-collected before it finishes.
        """
        task = asyncio.create_task(self._process_and_stream())
        if _task_holder is not None:
            _task_holder.append(task)
        try:
            while True:
                payload = await self.queue.get()
                if payload is None:
                    break
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            self.disconnected.set()
            raise
