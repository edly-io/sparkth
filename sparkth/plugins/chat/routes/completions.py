from datetime import datetime, timezone
from typing import Any, Literal, assert_never, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.exceptions import LangChainException
from langchain_core.tools import BaseTool
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.chat.hooks import ChatResponsibility, enabled_responsibilities
from sparkth.lib.db import get_async_session
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.i18n import _, gettext
from sparkth.lib.llm import (
    BaseChatProvider,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    get_llm_service,
    get_provider,
)
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.plugins.chat.analytics import (
    ChatAttachmentAnalytics,
    ChatClassifierAnalytics,
    ChatTurnAnalytics,
    TurnFailureCause,
    record_turn_failed,
)
from sparkth.plugins.chat.classifiers import MessageScopeClassifier, RAGSearchClassifier
from sparkth.plugins.chat.config import ChatSettings, get_chat_settings
from sparkth.plugins.chat.constants import LLM_PROVIDER_API_ERRORS, REDIRECT_MESSAGE, REFUSAL_MESSAGE
from sparkth.plugins.chat.conversation_title import extract_title_from_messages
from sparkth.plugins.chat.exceptions import RAGSearchError
from sparkth.plugins.chat.lms_credentials import build_lms_credentials_message
from sparkth.plugins.chat.messages import get_last_user_text
from sparkth.plugins.chat.models import Conversation, Message
from sparkth.plugins.chat.prompt import render_system_prompt
from sparkth.plugins.chat.responsibilities import stored_responsibility, turn_reply
from sparkth.plugins.chat.routes.utils import resolve_tools
from sparkth.plugins.chat.routes.utils.live_turns import request_stop
from sparkth.plugins.chat.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.chat.routes.utils.non_streaming import complete_without_stream
from sparkth.plugins.chat.routes.utils.stream_processor import (
    ChatStreamProcessor,
    stream_out_of_scope_refusal,
    streaming_error_message,
)
from sparkth.plugins.chat.routes.utils.turn_context import TurnContext
from sparkth.plugins.chat.routes.utils.turn_setup import record_incoming_turn
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


def _unusable_status(document: Document) -> Literal["queued", "processing", "failed"]:
    """Why this turn could not read an attached document."""
    match document.status:
        case DocumentStatus.QUEUED:
            return "queued"
        case DocumentStatus.PROCESSING:
            return "processing"
        case DocumentStatus.FAILED:
            return "failed"
        case DocumentStatus.READY:
            logger.warning("READY document %s listed unusable; is_deleted=%s", document.id, document.is_deleted)
            return "failed"
        case _ as unhandled:
            assert_never(unhandled)


def _refusal_response(
    message: str,
    stream: bool,
    conversation_uuid: UUID | None,
    model: str,
    provider_name: str,
) -> StreamingResponse | ChatCompletionResponse:
    """A fixed reply (the refusal or the redirect) that ends the turn, in the shape the client asked for.

    ``message`` is the refusal or the redirect source constant, rendered under the request
    locale. ``conversation_uuid`` is None when the turn was refused before any conversation was
    written, which is the answer the client gets rather than a missing field.
    """
    if stream:
        return StreamingResponse(stream_out_of_scope_refusal(message), media_type="text/event-stream")
    return ChatCompletionResponse(
        message=ChatMessage(role="assistant", content=gettext(message)),
        conversation_id=conversation_uuid,
        model=model,
        provider=provider_name,
    )


async def _resolve_llm_config(
    request: ChatCompletionRequest,
    user_id: int,
    session: AsyncSession,
    service: ChatService,
    llm_service: LLMConfigService,
) -> tuple[str, str, str]:
    """Return the turn's provider name, model (override applied) and decrypted API key.

    An unusable AI key fails the turn with one status and one thing the user can do about it per
    reason: missing is a 404, no model a 422, deactivated a 409. The failure is stored on the
    conversation and recorded as a failed turn before the error is raised.
    """
    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=user_id,
            config_id=request.llm_config_id,
        )
    except (LLMConfigNotFoundError, LLMConfigModelNotSetError, LLMConfigInactiveError) as exc:
        if isinstance(exc, LLMConfigNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
            detail = _("No AI Key found for the current user. Please configure an AI key in your chat plugin settings.")
        elif isinstance(exc, LLMConfigModelNotSetError):
            status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
            detail = _("The selected AI key has no model configured. Go to AI Keys to set a model before chatting.")
        else:
            status_code = status.HTTP_409_CONFLICT
            detail = _(
                "The selected AI key is deactivated. Go to AI Keys to reactivate it, "
                "or choose a different one in chat settings."
            )
        logger.warning(
            "LLMConfig %s unusable for user %s: %s: %s", request.llm_config_id, user_id, type(exc).__name__, exc
        )
        await service.record_error_message(session, request.conversation_id, user_id, detail)
        record_turn_failed(
            conversation_id=str(request.conversation_id) if request.conversation_id else None,
            provider=None,
            model=None,
            cause=TurnFailureCause.LLM_CONFIG_UNUSABLE,
            streamed=request.stream,
            actor_id=str(user_id),
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return llm_config.provider, request.model_override or llm_config.model, api_key


async def _ready_attachments(
    conversation_id: int, turn: TurnContext, attachment_analytics: ChatAttachmentAnalytics
) -> list[Document]:
    """Return the conversation's ingested documents, queueing ``attachment_unusable`` for the rest.

    An unusable document is attached as far as the instructor is concerned but not ingestible, so
    the turn runs as though it were not there. Nothing records the moment a document was passed
    over, so the event is stamped here.
    """
    conversation_documents = await turn.service.list_conversation_attachments(
        session=turn.session, conversation_id=conversation_id
    )
    for unusable in conversation_documents.unusable:
        attachment_analytics.schedule_attachment_unusable(
            document_id=cast(int, unusable.id),
            status=_unusable_status(unusable),
            occurred_at=datetime.now(timezone.utc),
        )
    return conversation_documents.ready


async def _judged_turn_end(
    scope_classifier: MessageScopeClassifier,
    db_messages: list[Message],
    attached_document_names: list[str],
    conversation: Conversation,
    responsibility: ChatResponsibility,
    turn: TurnContext,
) -> str | None:
    """Judge a later turn against the conversation's job; return the fixed reply that ends it, or None.

    The classifier sees the stored history without the message being judged, and the names of the
    ingested documents plus anything uploaded with this message, which has no row.
    """
    prior_history: list[HistoryTurn] = [
        {"role": m.role, "content": m.content}
        for m in db_messages
        if m is not db_messages[-1] or not (m.role == "user" and m.content == turn.query_text)
    ]
    turn_attachment_names = list(dict.fromkeys(attached_document_names + turn.request_attachment_names))
    judged = await scope_classifier.responsibility_for(
        turn.query_text,
        prior_history,
        turn_attachment_names or None,
        conversation.uuid,
        responsibility.name,
    )
    turn_end = turn_reply(judged, responsibility.name)
    if turn_end == REDIRECT_MESSAGE:
        logger.info(
            "Redirected conversation %s: stored job %s, judged job %s",
            conversation.uuid,
            responsibility.name,
            judged,
        )
    return turn_end


async def _rag_search_required(
    attached_documents: list[Document], conversation: Conversation, turn: TurnContext
) -> bool:
    """Whether the turn retrieves from its documents; asked only with something to search and to search for."""
    if not (attached_documents and turn.query_text):
        return False
    search_classifier = RAGSearchClassifier(turn.provider_name, turn.api_key, turn.user_id, turn.classifier_analytics)
    return await search_classifier.requires_search(turn.query_text, attached_documents, conversation.uuid)


async def _add_tool_guidance(
    tools: list[BaseTool] | None, messages: list[dict[str, Any]], provider: BaseChatProvider, turn: TurnContext
) -> None:
    """Tell the model about its bound tools: a tool-list system turn when asked, and LMS credentials."""
    if tools and turn.request.include_system_tools_message:
        tool_descriptions = [f"- {tool.name}: {tool.description}" for tool in tools]
        tool_list_message = "You have access to the following tools:\n" + "\n".join(tool_descriptions)
        messages.insert(0, {"role": "system", "content": tool_list_message})

    lms_credentials_message = await build_lms_credentials_message(
        session=turn.session,
        user_id=turn.user_id,
        tools=tools,
    )
    if lms_credentials_message:
        provider.system_prompt += f"\n\n{lms_credentials_message}"


def _stream_response(
    provider: BaseChatProvider,
    messages: list[dict[str, Any]],
    tools: list[BaseTool] | None,
    unresolved_messages: list[ChatMessage] | None,
    rag_search_required: bool,
    rag_search_declined: bool,
    conversation: Conversation,
    turn: TurnContext,
    turn_analytics: ChatTurnAnalytics,
) -> StreamingResponse:
    """Stream the turn's reply over SSE.

    The retrieval turn and its LLM are gated together so no LLM is built for a turn that will not
    retrieve. A turn is stoppable only if the caller named it (scripts and the MCP surface do not);
    the stream task registers and releases it, so a request that never gets that far leaves the
    registry untouched. The stream task outlives this response, writing its analytics after the
    SSE sentinel, so the holder keeps it referenced until it finishes.
    """
    rag_unresolved = unresolved_messages if rag_search_required else None
    rag_llm = provider.create_llm() if rag_search_required else None
    turn_key = str(turn.request.turn_id) if turn.request.turn_id else None
    processor = ChatStreamProcessor(
        provider,
        messages,
        conversation,
        turn.service,
        tools,
        rag_unresolved,
        turn.user_id,
        rag_llm,
        rag_search_required,
        rag_search_declined,
        analytics=turn_analytics.attribution,
        turn_id=turn_key,
    )
    return StreamingResponse(processor.stream(), media_type="text/event-stream")


async def _answer_turn(
    turn: TurnContext,
    scope_classifier: MessageScopeClassifier,
    conversation: Conversation,
    responsibility: ChatResponsibility,
    db_messages: list[Message],
    turn_analytics: ChatTurnAnalytics,
    attachment_analytics: ChatAttachmentAnalytics,
) -> StreamingResponse | ChatCompletionResponse:
    """Answer an opened conversation's turn: end it with a fixed reply, stream it, or reply whole.

    A first message was already judged for scope before its conversation was opened, so only a
    later turn is judged here. The conversation's job decides the system prompt and the tools.
    """
    conversation_id = cast(int, conversation.id)
    attached_documents = await _ready_attachments(conversation_id, turn, attachment_analytics)
    turn_end: str | None = None
    if turn.request.conversation_id:
        attached_document_names = [document.name for document in attached_documents]
        turn_end = await _judged_turn_end(
            scope_classifier, db_messages, attached_document_names, conversation, responsibility, turn
        )
    if turn_end is not None:
        await turn.service.add_message(
            session=turn.session,
            conversation_id=conversation_id,
            role="assistant",
            content=gettext(turn_end),
            message_type="text",
        )
        return _refusal_response(turn_end, turn.request.stream, conversation.uuid, turn.model, turn.provider_name)

    provider = get_provider(
        provider_name=turn.provider_name,
        api_key=turn.api_key,
        model=turn.model,
        system_prompt=render_system_prompt(responsibility),
        temperature=turn.request.temperature,
        max_tool_executions=turn.config.max_tool_executions,
    )
    rag_search_required = await _rag_search_required(attached_documents, conversation, turn)
    # A skip is worth telling the client about only when the classifier weighed it.
    rag_search_declined = bool(attached_documents) and bool(turn.query_text) and not rag_search_required
    messages, unresolved_messages = await assemble_provider_messages(
        turn.request, db_messages, attached_documents, turn.query_text, rag_search_required, provider
    )
    tools = await resolve_tools(turn.request, responsibility, get_tool_registry())
    await _add_tool_guidance(tools, messages, provider, turn)

    if turn.request.stream:
        return _stream_response(
            provider,
            messages,
            tools,
            unresolved_messages,
            rag_search_required,
            rag_search_declined,
            conversation,
            turn,
            turn_analytics,
        )
    return await complete_without_stream(
        provider, messages, tools, rag_search_required, conversation, turn, turn_analytics
    )


async def _upstream_failure(exc: Exception, conversation: Conversation, turn: TurnContext) -> HTTPException:
    """Record a turn an upstream service failed (retrieval intent or the provider) and return its 502.

    The conversation keeps the error message so a reload still shows what happened.
    """
    detail = (
        _("Failed to determine retrieval intent. Please try again.")
        if isinstance(exc, RAGSearchError)
        else streaming_error_message(exc)
    )
    logger.error("Conversation %s failed on %s: %s", conversation.id, type(exc).__name__, exc)
    await turn.service.add_message(
        session=turn.session,
        conversation_id=cast(int, conversation.id),
        role="assistant",
        content=detail,
        is_error=True,
    )
    record_turn_failed(
        conversation_id=str(conversation.uuid),
        provider=turn.provider_name,
        model=turn.model,
        cause=(
            TurnFailureCause.RAG_SEARCH_ERROR
            if isinstance(exc, RAGSearchError)
            else TurnFailureCause.PROVIDER_API_ERROR
        ),
        streamed=turn.request.stream,
        actor_id=str(turn.user_id),
    )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _unexpected_failure(exc: Exception, conversation: Conversation, turn: TurnContext) -> HTTPException:
    """Record a turn that failed unexpectedly and return its 500."""
    logger.error("Chat completion failed: %s", exc)
    record_turn_failed(
        conversation_id=str(conversation.uuid),
        provider=turn.provider_name,
        model=turn.model,
        cause=TurnFailureCause.UNEXPECTED,
        streamed=turn.request.stream,
        actor_id=str(turn.user_id),
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=_("Chat completion failed"),
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
) -> StreamingResponse | ChatCompletionResponse:
    """Answer one chat turn, streamed over SSE or as one JSON reply.

    Resolves the AI key and judges a first message for scope before anything is written. Then it
    opens the conversation, records the incoming turn and answers it under the conversation's job.
    An upstream failure is a 502, an unexpected one a 500; both are recorded as failed turns.
    """
    user_id: int = cast(int, current_user.id)
    provider_name, model, api_key = await _resolve_llm_config(request, user_id, session, service, llm_service)
    classifier_analytics = ChatClassifierAnalytics(
        background_tasks=background_tasks, provider=provider_name, actor_id=str(user_id)
    )
    turn = TurnContext(
        request=request,
        user_id=user_id,
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        query_text=get_last_user_text(request.messages),
        request_attachment_names=[m.attachment.name for m in request.messages if m.attachment],
        classifier_analytics=classifier_analytics,
        session=session,
        service=service,
        config=config,
        background_tasks=background_tasks,
    )
    # The jobs offered on this request; a switched-off plugin's job is left out.
    jobs = await enabled_responsibilities(session)
    scope_classifier = MessageScopeClassifier(jobs, provider_name, api_key, user_id, classifier_analytics)

    first_responsibility: str | None = None
    if not request.conversation_id:
        first_responsibility = await scope_classifier.responsibility_for(
            turn.query_text, [], turn.request_attachment_names, None
        )
        if first_responsibility is None:
            return _refusal_response(REFUSAL_MESSAGE, request.stream, None, model, provider_name)

    conversation, conversation_was_created = await service.get_or_create_conversation(
        session,
        conversation_uuid=request.conversation_id,
        user_id=user_id,
        llm_config_id=request.llm_config_id,
        provider=provider_name,
        model=model,
        title=extract_title_from_messages(request.messages, max_length=config.title_max_length),
        responsibility=first_responsibility,
    )
    # The job this conversation does decides the turn's reply, system prompt and tools.
    responsibility = stored_responsibility(conversation, jobs)
    turn_analytics, attachment_analytics = await record_incoming_turn(conversation, conversation_was_created, turn)
    db_messages = await service.get_conversation_messages(session=session, conversation_id=cast(int, conversation.id))

    try:
        return await _answer_turn(
            turn, scope_classifier, conversation, responsibility, db_messages, turn_analytics, attachment_analytics
        )
    except (RAGSearchError, *LLM_PROVIDER_API_ERRORS) as exc:
        raise await _upstream_failure(exc, conversation, turn) from exc
    except (ValueError, RuntimeError, ValidationError, LangChainException) as exc:
        raise _unexpected_failure(exc, conversation, turn) from exc


@router.post("/turns/{turn_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_turn(turn_id: UUID, current_user: User = Depends(get_current_user)) -> None:
    """Ask a streaming turn to stop. 404 covers both an unknown turn and another user's."""
    if not request_stop(str(turn_id), cast(int, current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("No generation is running for this turn."),
        )
