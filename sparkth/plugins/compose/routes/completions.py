from datetime import datetime, timezone
from typing import Any, Literal, assert_never, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.compose.hooks import enabled_agents
from sparkth.lib.db import get_async_session
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.i18n import _
from sparkth.lib.llm import (
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    get_llm_service,
    get_provider,
    small_model_for,
)
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.lib.permissions.scopes import USER
from sparkth.lib.plugins import get_disabled_plugins
from sparkth.plugins.compose.analytics import (
    ComposeAttachmentAnalytics,
    ComposeClassifierAnalytics,
    ComposeTurnAnalytics,
    TurnFailureCause,
    executed_tools_from,
    record_turn_failed,
)
from sparkth.plugins.compose.classifiers import RAGSearchClassifier
from sparkth.plugins.compose.config import ComposeSettings, get_compose_settings
from sparkth.plugins.compose.constants import LLM_PROVIDER_API_ERRORS
from sparkth.plugins.compose.conversation_title import extract_title_from_messages, schedule_title_generation
from sparkth.plugins.compose.exceptions import RAGSearchError
from sparkth.plugins.compose.llm import complete_turn
from sparkth.plugins.compose.messages import get_last_user_text
from sparkth.plugins.compose.permissions import CONVERSATION_WRITE
from sparkth.plugins.compose.routes.dependencies import get_turn_owner_id
from sparkth.plugins.compose.routes.utils import resolve_tools
from sparkth.plugins.compose.routes.utils.live_turns import request_stop
from sparkth.plugins.compose.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.compose.routes.utils.stream_processor import (
    ComposeStreamProcessor,
    streaming_error_message,
)
from sparkth.plugins.compose.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from sparkth.plugins.compose.service import ComposeService, get_compose_service
from sparkth.plugins.compose.tools import get_tool_registry

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
    dependencies=[Depends(CONVERSATION_WRITE.require_for_object(USER, get_turn_owner_id))],
)
async def compose_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    owner_id: str = Depends(get_turn_owner_id),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
    llm_service: LLMConfigService = Depends(get_llm_service),
    config: ComposeSettings = Depends(get_compose_settings),
    disabled_plugins: set[str] = Depends(get_disabled_plugins),
) -> Any:
    # The caller runs the turn; the conversation and what it stores belong to owner_id.
    user_id: int = cast(int, current_user.id)
    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=user_id,
            config_id=request.llm_config_id,
        )
    except (LLMConfigNotFoundError, LLMConfigModelNotSetError, LLMConfigInactiveError) as exc:
        # One status and one thing the user can do about it, per reason. Only the tail below is
        # shared, which is all that was ever written three times.
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
        await service.record_error_message(session, request.conversation_id, detail)
        record_turn_failed(
            conversation_id=str(request.conversation_id) if request.conversation_id else None,
            provider=None,
            model=None,
            cause=TurnFailureCause.LLM_CONFIG_UNUSABLE,
            streamed=request.stream,
            actor_id=str(user_id),
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc

    provider_name = llm_config.provider
    model = request.model_override or llm_config.model
    conversation_uuid = request.conversation_id
    query_text = get_last_user_text(request.messages)
    classifier_analytics = ComposeClassifierAnalytics(
        background_tasks=background_tasks,
        provider=provider_name,
        actor_id=str(user_id),
    )
    # The tool filter and the agent list share one set of switched-off plugins.
    agents = enabled_agents(disabled_plugins)

    conversation, conversation_was_created = await service.get_or_create_conversation(
        session,
        conversation_uuid=conversation_uuid,
        user_id=int(owner_id),
        llm_config_id=request.llm_config_id,
        provider=provider_name,
        model=model,
        title=extract_title_from_messages(request.messages, max_length=config.title_max_length),
    )
    conversation_id = cast(int, conversation.id)
    turn_analytics = ComposeTurnAnalytics(
        background_tasks=background_tasks,
        conversation_id=str(conversation.uuid),
        provider=provider_name,
        model=model,
        actor_id=str(user_id),
    )
    attachment_analytics = ComposeAttachmentAnalytics(
        background_tasks=background_tasks,
        conversation_id=str(conversation.uuid),
        actor_id=str(user_id),
    )
    if conversation_was_created:
        schedule_title_generation(
            background_tasks,
            service,
            conversation_id=conversation_id,
            user_id=int(owner_id),
            messages=request.messages,
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            config=config,
        )
        # Queued after the title task, not before. Starlette runs the background queue as a
        # plain sequential loop with no per-task isolation, and analytics emits propagate
        # their failures by design, so an emit queued first would let an analytics outage
        # silently cost the conversation its title. Keep analytics last in this queue.
        # Timed by the row, not by this call: this task runs only after the response has
        # completed, which for a streamed turn is after the whole stream.
        turn_analytics.schedule_conversation_started(occurred_at=conversation.created_at)

    if request.document_ids:
        attached = await service.attach_owned_documents(session, conversation_id, request.document_ids, int(owner_id))
        for attachment in attached.created:
            attachment_analytics.schedule_document_attached(
                document_id=attachment.document_id,
                source="completion_request",
                occurred_at=attachment.attached_at,
            )
        if attached.skipped_count:
            # The instructor named documents that were dropped and the reply says nothing
            # about it, so this is the only record that their turn was not what they asked
            # for. Nothing records the moment, so it is stamped here.
            attachment_analytics.schedule_documents_skipped(
                requested_count=attached.requested_count,
                skipped_count=attached.skipped_count,
                occurred_at=datetime.now(timezone.utc),
            )
    incoming_messages = await service.add_incoming_messages(session, conversation_id, request.messages)
    for stored in incoming_messages:
        # Instructor turns only: an assistant turn in the request is history the client
        # replayed, and assistant output is counted by compose.completion_served instead.
        if stored.role != "user":
            continue
        turn_analytics.schedule_message_sent(
            message_length=len(stored.content),
            has_attachment=stored.message_type == "attachment",
            occurred_at=stored.created_at,
        )

    db_messages = await service.get_conversation_messages(session=session, conversation_id=conversation_id)

    try:
        # The search classifier judges the message against these.
        conversation_documents = await service.list_conversation_attachments(
            session=session, conversation_id=conversation_id
        )
        attached_documents = conversation_documents.ready
        for unusable in conversation_documents.unusable:
            # Attached as far as the instructor is concerned, but not ingestible, so this
            # turn runs as though it were not there. Stamped here: nothing records the
            # moment a document was passed over.
            attachment_analytics.schedule_attachment_unusable(
                document_id=cast(int, unusable.id),
                status=_unusable_status(unusable),
                occurred_at=datetime.now(timezone.utc),
            )

        provider = get_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            temperature=request.temperature,
        )
        # The planner picks who answers, so it runs on the provider's smallest model.
        planner_llm = get_provider(provider_name, api_key, small_model_for(provider_name), temperature=0).create_llm()

        # Only asked when there is something to search and something to search for.
        rag_search_required = False
        if attached_documents and query_text:
            search_classifier = RAGSearchClassifier(provider_name, api_key, user_id, classifier_analytics)
            rag_search_required = await search_classifier.requires_search(
                query_text, attached_documents, conversation.uuid
            )
        # A skip is worth telling the client about only when the classifier weighed it.
        rag_search_declined = bool(attached_documents) and bool(query_text) and not rag_search_required

        messages, unresolved_messages = await assemble_provider_messages(
            request,
            db_messages,
            attached_documents,
            query_text,
            rag_search_required,
            provider,
            analytics=turn_analytics,
        )

        tools = await resolve_tools(request, get_tool_registry(), disabled_plugins)

        if request.stream:
            # Gated together so no LLM is built for a turn that will not retrieve.
            rag_unresolved = unresolved_messages if rag_search_required else None
            rag_llm = provider.create_llm() if rag_search_required else None
            # A turn is stoppable only if the caller named it; scripts and the MCP surface do not.
            # The stream task registers and releases it, so a request that never gets that far
            # leaves the registry untouched.
            turn_key = str(request.turn_id) if request.turn_id else None
            processor = ComposeStreamProcessor(
                provider,
                messages,
                conversation,
                service,
                tools,
                rag_unresolved,
                user_id,
                rag_llm,
                rag_search_required,
                rag_search_declined,
                analytics=turn_analytics.attribution,
                turn_id=turn_key,
                max_tool_executions=config.max_tool_executions,
                agents=agents,
                planner_llm=planner_llm,
            )
            return StreamingResponse(
                # The stream task outlives this response — it writes its analytics after the
                # SSE sentinel — so the holder keeps it referenced until it finishes.
                processor.stream(),
                media_type="text/event-stream",
            )
        else:
            response = await complete_turn(
                messages, tools or [], provider, config.max_tool_executions, agents=agents, planner_llm=planner_llm
            )

            tokens_used = response.get("metadata", {}).get("usage_metadata", {}).get("total_tokens")
            tool_calls = response.get("tool_calls")

            assistant_message = await service.add_message(
                session=session,
                conversation_id=conversation_id,
                role="assistant",
                content=response["content"],
                tokens_used=tokens_used,
                metadata=response.get("metadata"),
                message_type="text",
            )

            # Executions live under metadata: response["tool_calls"] is always None, so reading
            # it would count zero forever.
            response_metadata = response.get("metadata") or {}
            executions = response_metadata.get("tool_executions") or []
            turn_analytics.schedule_completion(
                rag_used=rag_search_required,
                streamed=False,
                executed_tools=executed_tools_from(executions),
                occurred_at=assistant_message.created_at,
                routing=response["routing"],
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
        # Each is an upstream service failing the turn: the user is told, and the conversation
        # keeps the message so a reload still shows what happened.
        if isinstance(exc, RAGSearchError):
            detail = _("Failed to determine retrieval intent. Please try again.")
            cause = TurnFailureCause.RAG_SEARCH_ERROR
        else:
            detail = streaming_error_message(exc)
            cause = TurnFailureCause.PROVIDER_API_ERROR
        logger.error("Conversation %s failed on %s: %s", conversation_id, type(exc).__name__, exc)
        await service.add_message(
            session=session,
            conversation_id=conversation_id,
            role="assistant",
            content=detail,
            is_error=True,
        )
        record_turn_failed(
            conversation_id=str(conversation.uuid),
            provider=provider_name,
            model=model,
            cause=cause,
            streamed=request.stream,
            actor_id=str(user_id),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    except (ValueError, RuntimeError, ValidationError, LangChainException) as e:
        logger.error("Chat completion failed: %s", e)
        record_turn_failed(
            conversation_id=str(conversation.uuid),
            provider=provider_name,
            model=model,
            cause=TurnFailureCause.UNEXPECTED,
            streamed=request.stream,
            actor_id=str(user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_("Chat completion failed"),
        ) from e


@router.post("/turns/{turn_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_turn(turn_id: UUID, current_user: User = Depends(get_current_user)) -> None:
    """Ask a streaming turn to stop. 404 covers both an unknown turn and another user's."""
    if not request_stop(str(turn_id), cast(int, current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("No generation is running for this turn."),
        )
