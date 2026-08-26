from typing import Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _, gettext
from sparkth.lib.llm import (
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    get_llm_service,
    get_provider,
)
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.plugins.chat.classifiers import MessageScopeClassifier, RAGSearchClassifier
from sparkth.plugins.chat.config import ChatSettings, get_chat_settings
from sparkth.plugins.chat.constants import LLM_PROVIDER_API_ERRORS
from sparkth.plugins.chat.conversation_title import extract_title_from_messages, schedule_title_generation
from sparkth.plugins.chat.exceptions import RAGSearchError
from sparkth.plugins.chat.lms_credentials import build_lms_credentials_message
from sparkth.plugins.chat.messages import extract_query_text
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt
from sparkth.plugins.chat.routes.utils import resolve_tools
from sparkth.plugins.chat.routes.utils.rag_search import resolve_document_blocks
from sparkth.plugins.chat.routes.utils.stream_processor import (
    ChatStreamProcessor,
    stream_out_of_scope_refusal,
    streaming_error_message,
)
from sparkth.plugins.chat.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    HistoryTurn,
)
from sparkth.plugins.chat.service import ChatService, get_chat_service
from sparkth.plugins.chat.tools import get_tool_registry

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
        detail = _("No AI Key found for the current user. Please configure an AI key in your chat plugin settings.")
        await service.record_error_message(session, request.conversation_id, user_id, detail)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    except LLMConfigModelNotSetError as exc:
        logger.warning("LLMConfig %s has no model set: %s", request.llm_config_id, exc)
        detail = _("The selected AI key has no model configured. Go to AI Keys to set a model before chatting.")
        await service.record_error_message(session, request.conversation_id, user_id, detail)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail) from exc
    except LLMConfigInactiveError as exc:
        logger.warning("LLMConfig %s is inactive for user %s: %s", request.llm_config_id, current_user.id, exc)
        detail = _(
            "The selected AI key is deactivated. Go to AI Keys to reactivate it, "
            "or choose a different one in chat settings."
        )
        await service.record_error_message(session, request.conversation_id, user_id, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model
    conversation_uuid = request.conversation_id
    query_text = extract_query_text(request.messages)
    scope_classifier = MessageScopeClassifier(provider_name, api_key)

    # A file uploaded with the message is base64 content, not a Document row, so its name exists
    # only here — both scope checks below need it.
    request_attachment_names = [m.attachment.name for m in request.messages if m.attachment]

    # Judged above get_or_create_conversation so an out-of-scope first message writes no row.
    _skip_main_scope_check = False
    if not conversation_uuid:
        # Nothing is persisted yet, and there is no uuid to log a refusal against.
        if not await scope_classifier.in_scope(query_text, [], request_attachment_names, None):
            if request.stream:
                return StreamingResponse(
                    stream_out_of_scope_refusal(),
                    media_type="text/event-stream",
                )
            return ChatCompletionResponse(
                message=ChatMessage(role="assistant", content=gettext(REFUSAL_MESSAGE)),
                conversation_id=None,
                model=model,
                provider=provider_name,
            )
        # Already judged, so the check below would spend a second call on the same message.
        _skip_main_scope_check = True

    conversation, conversation_was_created = await service.get_or_create_conversation(
        session,
        conversation_uuid=conversation_uuid,
        user_id=user_id,
        llm_config_id=request.llm_config_id,
        provider=provider_name,
        model=model,
        title=extract_title_from_messages(request.messages, max_length=config.title_max_length),
    )
    if conversation_was_created:
        schedule_title_generation(
            background_tasks,
            service,
            conversation_id=cast(int, conversation.id),
            user_id=user_id,
            messages=request.messages,
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            config=config,
        )

    if request.document_ids:
        await service.attach_owned_documents(session, cast(int, conversation.id), request.document_ids, user_id)
    await service.add_incoming_messages(session, cast(int, conversation.id), request.messages)

    db_messages = await service.get_conversation_messages(
        session=session,
        conversation_id=cast(int, conversation.id),
    )

    try:
        # Both classifiers need these: scope, to know documents are in play, and search, to
        # judge the message against them.
        attached_documents = await service.list_conversation_attachments(
            session=session,
            conversation_id=cast(int, conversation.id),
        )
        attached_document_names = [document.name for document in attached_documents]

        if not _skip_main_scope_check:
            prior_history: list[HistoryTurn] = [
                {"role": m.role, "content": m.content}
                for m in db_messages
                if m is not db_messages[-1] or not (m.role == "user" and m.content == query_text)
            ]
            # Ingested documents plus anything uploaded with this message, which has no row.
            turn_attachment_names = list(dict.fromkeys(attached_document_names + request_attachment_names))
            _in_scope = await scope_classifier.in_scope(
                query_text,
                prior_history,
                turn_attachment_names or None,
                conversation.uuid,
            )
        else:
            _in_scope = True

        if not _in_scope:
            await service.add_message(
                session=session,
                conversation_id=cast(int, conversation.id),
                role="assistant",
                content=gettext(REFUSAL_MESSAGE),
                message_type="text",
            )
            if request.stream:
                return StreamingResponse(
                    stream_out_of_scope_refusal(),
                    media_type="text/event-stream",
                )
            return ChatCompletionResponse(
                message=ChatMessage(role="assistant", content=gettext(REFUSAL_MESSAGE)),
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

        # Only asked when there is something to search and something to search for.
        rag_search_required = False
        if attached_documents and query_text:
            search_classifier = RAGSearchClassifier(provider_name, api_key)
            rag_search_required = await search_classifier.requires_search(
                query_text, attached_documents, conversation.uuid
            )
        # A skip is worth telling the client about only when the classifier weighed it.
        rag_search_declined = bool(attached_documents) and bool(query_text) and not rag_search_required

        # Use DB messages for history, but replace the current batch with original
        # request content to preserve content blocks (e.g. base64 document attachments).
        num_current = len(request.messages)
        history: list[dict[str, Any]] = (
            [{"role": m.role, "content": m.content} for m in db_messages[:-num_current]]
            if len(db_messages) > num_current
            else []
        )

        unresolved_messages: list[ChatMessage] | None = None
        if rag_search_required and attached_documents:
            # One synthetic turn: document blocks for retrieval to resolve, plus the query text
            # so it survives that resolution.
            document_blocks: list[dict[str, Any]] = [
                {"type": "drive_file", "file_id": document.id} for document in attached_documents
            ]
            text_block: list[dict[str, Any]] = [{"type": "text", "text": query_text}] if query_text else []
            unresolved_messages = [ChatMessage(role="user", content=document_blocks + text_block)]

        if request.stream and rag_search_required:
            # Sent unresolved: the stream replaces the document blocks with retrieved context,
            # keeping the query text beside it.
            if unresolved_messages is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=_("Chat completion failed"),
                )
            current: list[dict[str, Any]] = [{"role": msg.role, "content": msg.content} for msg in unresolved_messages]
        else:
            if rag_search_required and unresolved_messages:
                # Resolved up front, since there is no stream to do it in.
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
            # Gated together so no LLM is built for a turn that will not retrieve.
            rag_unresolved = unresolved_messages if rag_search_required else None
            rag_user_id = user_id if rag_search_required else None
            rag_llm = provider.create_llm() if rag_search_required else None
            processor = ChatStreamProcessor(
                provider,
                messages,
                conversation,
                service,
                tools,
                rag_unresolved,
                rag_user_id,
                rag_llm,
                rag_search_required,
                rag_search_declined,
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

    except RAGSearchError as e:
        logger.error("RAG intent router failed for user %s conversation %s: %s", current_user.id, conversation.id, e)
        detail = _("Failed to determine retrieval intent. Please try again.")
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
            detail=_("Chat completion failed"),
        ) from e
