from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _, gettext, gettext_noop
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
from sparkth.plugins.chat.constants import LLM_PROVIDER_API_ERRORS, REFUSAL_MESSAGE
from sparkth.plugins.chat.conversation_title import extract_title_from_messages, schedule_title_generation
from sparkth.plugins.chat.exceptions import RAGSearchError
from sparkth.plugins.chat.lms_credentials import build_lms_credentials_message
from sparkth.plugins.chat.messages import get_last_user_text
from sparkth.plugins.chat.prompt import get_course_design_system_prompt
from sparkth.plugins.chat.routes.utils import resolve_tools
from sparkth.plugins.chat.routes.utils.message_assembly import assemble_provider_messages
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

# Why a request cannot use the config it named. Each is one status and one thing the user can do
# about it, so the mapping is the whole decision. gettext_noop marks the copy for extraction; it is
# rendered at raise time under the request's locale.
_UNUSABLE_CONFIG: dict[type[Exception], tuple[int, str]] = {
    LLMConfigNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        gettext_noop("No AI Key found for the current user. Please configure an AI key in your chat plugin settings."),
    ),
    LLMConfigModelNotSetError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        gettext_noop("The selected AI key has no model configured. Go to AI Keys to set a model before chatting."),
    ),
    LLMConfigInactiveError: (
        status.HTTP_409_CONFLICT,
        gettext_noop(
            "The selected AI key is deactivated. Go to AI Keys to reactivate it, "
            "or choose a different one in chat settings."
        ),
    ),
}


def _unusable_config_failure(exc: Exception) -> tuple[int, str]:
    """The status and message for a config failure, matched by class rather than by identity so a
    subclass is not a KeyError inside an except block."""
    for failure_type, failure in _UNUSABLE_CONFIG.items():
        if isinstance(exc, failure_type):
            return failure
    raise exc


def _refusal_response(
    stream: bool,
    conversation_uuid: UUID | None,
    model: str,
    provider_name: str,
) -> StreamingResponse | ChatCompletionResponse:
    """The out-of-scope refusal, in whichever shape the client asked for.

    ``conversation_uuid`` is None when the turn was refused before any conversation was written,
    which is the answer the client gets rather than a missing field.
    """
    if stream:
        return StreamingResponse(stream_out_of_scope_refusal(), media_type="text/event-stream")
    return ChatCompletionResponse(
        message=ChatMessage(role="assistant", content=gettext(REFUSAL_MESSAGE)),
        conversation_id=conversation_uuid,
        model=model,
        provider=provider_name,
    )


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
    except tuple(_UNUSABLE_CONFIG) as exc:
        status_code, message = _unusable_config_failure(exc)
        detail = gettext(message)
        logger.warning(
            "LLMConfig %s unusable for user %s: %s: %s", request.llm_config_id, user_id, type(exc).__name__, exc
        )
        await service.record_error_message(session, request.conversation_id, user_id, detail)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model
    conversation_uuid = request.conversation_id
    query_text = get_last_user_text(request.messages)
    scope_classifier = MessageScopeClassifier(provider_name, api_key, user_id)

    # A file uploaded with the message is base64 content, not a Document row, so its name exists
    # only here — both scope checks below need it.
    request_attachment_names = [m.attachment.name for m in request.messages if m.attachment]

    # Judged above get_or_create_conversation so an out-of-scope first message writes no row.
    _skip_main_scope_check = False
    if not conversation_uuid:
        # Nothing is persisted yet, and there is no uuid to log a refusal against.
        if not await scope_classifier.in_scope(query_text, [], request_attachment_names, None):
            return _refusal_response(request.stream, None, model, provider_name)
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
    conversation_id = cast(int, conversation.id)
    if conversation_was_created:
        schedule_title_generation(
            background_tasks,
            service,
            conversation_id=conversation_id,
            user_id=user_id,
            messages=request.messages,
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            config=config,
        )

    if request.document_ids:
        await service.attach_owned_documents(session, conversation_id, request.document_ids, user_id)
    await service.add_incoming_messages(session, conversation_id, request.messages)

    db_messages = await service.get_conversation_messages(session=session, conversation_id=conversation_id)

    try:
        # Both classifiers need these: scope, to know documents are in play, and search, to
        # judge the message against them.
        attached_documents = await service.list_conversation_attachments(
            session=session, conversation_id=conversation_id
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
                conversation_id=conversation_id,
                role="assistant",
                content=gettext(REFUSAL_MESSAGE),
                message_type="text",
            )
            return _refusal_response(request.stream, conversation.uuid, model, provider_name)

        provider = get_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            system_prompt=get_course_design_system_prompt(),
            temperature=request.temperature,
            max_tool_executions=config.max_tool_executions,
        )

        # Only asked when there is something to search and something to search for.
        rag_search_required = False
        if attached_documents and query_text:
            search_classifier = RAGSearchClassifier(provider_name, api_key, user_id)
            rag_search_required = await search_classifier.requires_search(
                query_text, attached_documents, conversation.uuid
            )
        # A skip is worth telling the client about only when the classifier weighed it.
        rag_search_declined = bool(attached_documents) and bool(query_text) and not rag_search_required

        messages, unresolved_messages = await assemble_provider_messages(
            request, db_messages, attached_documents, query_text, rag_search_required, provider
        )

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
                conversation_id=conversation_id,
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

    except (RAGSearchError, *LLM_PROVIDER_API_ERRORS) as exc:
        # Both are an upstream service failing the turn: the user is told, and the conversation
        # keeps the message so a reload still shows what happened.
        detail = (
            _("Failed to determine retrieval intent. Please try again.")
            if isinstance(exc, RAGSearchError)
            else streaming_error_message(exc)
        )
        logger.error("Conversation %s failed on %s: %s", conversation_id, type(exc).__name__, exc)
        await service.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content=detail,
            is_error=True,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    except (ValueError, RuntimeError, ValidationError, LangChainException) as e:
        logger.error("Chat completion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_("Chat completion failed"),
        ) from e
