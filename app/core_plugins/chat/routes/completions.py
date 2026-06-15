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
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core_plugins.chat.classifier import HistoryTurn
from app.core_plugins.chat.config import ChatSettings, get_chat_settings
from app.core_plugins.chat.constants import LLM_PROVIDER_API_ERRORS, RAG_CONTEXT_PROMPT
from app.core_plugins.chat.exceptions import RAGIntentRouterError
from app.core_plugins.chat.lms_credentials import build_lms_credentials_message
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt
from app.core_plugins.chat.routes.helpers import (
    attach_request_documents,
    classify_in_scope,
    collect_document_ids,
    extract_query_text,
    format_source_block,
    get_or_create_conversation,
    group_by_source,
    persist_incoming_messages,
    persist_pre_stream_error,
    resolve_document_blocks,
    resolve_rag_intent,
    resolve_tools,
    stream_out_of_scope_refusal,
)
from app.core_plugins.chat.schemas import ChatCompletionRequest, ChatCompletionResponse, ChatMessage
from app.core_plugins.chat.service import ChatService, get_chat_service
from app.core_plugins.chat.tools import get_tool_registry
from app.lib.db import get_async_session, session_scope
from app.lib.llm import (
    BaseChatProvider,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    get_llm_service,
    get_provider,
)
from app.lib.log import get_logger
from app.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    agentic_retrieve_context,
)
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
            stream_kwargs: dict[str, Any] = {}
            if should_run_rag and unresolved_messages:
                stream_kwargs = {
                    "unresolved_messages": unresolved_messages,
                    "user_id": current_user.id,
                    "llm": provider.create_llm(),
                    "should_run_rag": True,
                }
            elif attached_documents:
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

    def _build_rag_context(
        self, all_chunks: list[RetrievedChunk]
    ) -> tuple[dict[str, str], list[dict[str, str | None]]]:
        """Section deduplication prevents the same section appearing twice in the
        UI when multiple chunks come from the same chapter/section/subsection.
        """
        grouped = group_by_source(all_chunks)
        source_blocks: dict[str, str] = {
            source: format_source_block(source, src_chunks) for source, src_chunks in grouped.items()
        }
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
        return source_blocks, confirmed_rag_sections

    def _inject_rag_into_messages(self, source_blocks: dict[str, str]) -> None:
        """Mutates self.messages in-place to avoid copying large message lists."""
        rag_block_list: list[dict[str, Any]] = [{"type": "text", "text": text} for text in source_blocks.values()]
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

    async def _emit_rag_routing_status(self, document_ids: list[int]) -> None:
        await self._put(json.dumps({"status": "scanning_attachments", "file_count": len(document_ids), "done": False}))

    async def _retrieve_rag_chunks(
        self,
        query_text: str,
        document_ids: list[int],
        bg_session: AsyncSession,
    ) -> list[RetrievedChunk] | None:
        """Returns None when retrieval fails; the error SSE and DB write are already handled before returning."""
        await self._put(json.dumps({"status": "searching_documents", "file_count": len(document_ids), "done": False}))
        logger.info("Agentic RAG search for document_ids=%s query_len=%d", document_ids, len(query_text))
        if self.llm is None:
            raise AssertionError("llm must be provided when RAG resolution is active")
        try:
            return await agentic_retrieve_context(query_text, document_ids, self.llm)
        except DocumentNotFoundError as exc:
            logger.error("Agentic RAG failed for document_ids=%s: %s", document_ids, exc)
            error_text = "The attached document could not be found or is no longer accessible."
            await self.service.add_message(
                session=bg_session,
                conversation_id=self.conversation_id,
                role="assistant",
                content=error_text,
                is_error=True,
            )
            await self._put(json.dumps({"error": error_text, "done": True}))
            return None
        except RAGNotReadyError as exc:
            logger.error("Agentic RAG failed for document_ids=%s: %s", document_ids, exc)
            error_text = "The attached document is still being processed. Please wait a moment and try again."
            await self.service.add_message(
                session=bg_session,
                conversation_id=self.conversation_id,
                role="assistant",
                content=error_text,
                is_error=True,
            )
            await self._put(json.dumps({"error": error_text, "done": True}))
            return None
        except RAGRetrievalError as exc:
            logger.error("Agentic RAG failed for document_ids=%s: %s", document_ids, exc)
            error_text = "Failed to search the attached document. Please try again."
            await self.service.add_message(
                session=bg_session,
                conversation_id=self.conversation_id,
                role="assistant",
                content=error_text,
                is_error=True,
            )
            await self._put(json.dumps({"error": error_text, "done": True}))
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
        await self._put(json.dumps({"done": True, "content": no_chunks_msg, "conversation_id": self.conversation_uuid}))

    async def _emit_rag_section_events(self, confirmed_rag_sections: list[dict[str, str | None]]) -> None:
        """Two-pass emit (scanning then confirmed) lets the UI animate each section
        before marking it resolved, rather than all sections appearing at once.
        """
        for section in confirmed_rag_sections:
            await self._put(json.dumps({"status": "section_scanning", "section": section, "done": False}))
        for section in confirmed_rag_sections:
            await self._put(json.dumps({"status": "section_confirmed", "section": section, "done": False}))
        await self._put(json.dumps({"status": "generating", "done": False}))

    async def _run_rag_phase(self, bg_session: AsyncSession) -> list[dict[str, str | None]] | None:
        """Return value convention: None means the response is already complete (error or no-results handled);
        [] means RAG was skipped but the LLM phase should still run.
        """
        if not self.should_run_rag or not self.unresolved_messages or self.user_id is None:
            if self.rag_routing_reason is not None:
                await self._put(
                    json.dumps({"status": "skipping_rag", "reason": self.rag_routing_reason, "done": False})
                )
            return []

        document_ids = collect_document_ids(self.unresolved_messages)
        await self._emit_rag_routing_status(document_ids)

        query_text = extract_query_text(self.unresolved_messages)
        chunks = await self._retrieve_rag_chunks(query_text, document_ids, bg_session)
        if chunks is None:
            return None

        source_blocks, confirmed_rag_sections = self._build_rag_context(chunks)
        if not source_blocks:
            await self._emit_no_rag_results_response(bg_session)
            return None

        self._inject_rag_into_messages(source_blocks)
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
                    await self._put(json.dumps({"token": token, "done": False}))
                elif event["type"] == "tool_start":
                    await self._put(
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
                    await self._put(
                        json.dumps(
                            {
                                "status": "tool_call",
                                "tool_name": event["name"],
                                "tool_status": "done",
                                "done": False,
                            }
                        )
                    )
            return full_response, completed_tool_calls
        except LLM_PROVIDER_API_ERRORS as e:
            user_message = _streaming_error_message(e)
            logger.error("Streaming failed: %s", e)
            await self.service.add_message(
                session=bg_session,
                conversation_id=self.conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            await self._put(json.dumps({"error": user_message, "done": True}))
            return None
        except (OSError, LangChainException) as e:
            logger.exception("Unexpected streaming error: %s", e)
            user_message = "An error occurred while generating a response. Please try again."
            await self.service.add_message(
                session=bg_session,
                conversation_id=self.conversation_id,
                role="assistant",
                content=user_message,
                is_error=True,
            )
            await self._put(json.dumps({"error": user_message, "done": True}))
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
        await self._put(
            json.dumps(
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
                error_text = "An unexpected error occurred. Please try again."
                await self.service.add_message(
                    session=bg_session,
                    conversation_id=self.conversation_id,
                    role="assistant",
                    content=error_text,
                    is_error=True,
                )
                await self._put(json.dumps({"error": error_text, "done": True}))
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
) -> AsyncGenerator[str, None]:
    processor = ChatStreamProcessor(
        provider,
        messages,
        conversation,
        service,
        tools,
        unresolved_messages,
        user_id,
        llm,
        should_run_rag,
        rag_routing_reason,
    )
    async for chunk in processor.stream(_task_holder):
        yield chunk


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
