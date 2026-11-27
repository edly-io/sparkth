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
from sparkth.lib.permissions import PLUGIN_USE, get_accessible_scope_object_ids
from sparkth.lib.permissions.scopes import PLUGIN
from sparkth.lib.plugins import get_disabled_plugins
from sparkth.lib.rag import bind_readable_document_ids
from sparkth.plugins.compose.analytics import (
    ComposeAttachmentAnalytics,
    ComposeTurnAnalytics,
    TurnFailureCause,
    executed_tools_from,
    record_turn_failed,
)
from sparkth.plugins.compose.config import ComposeSettings, get_compose_settings
from sparkth.plugins.compose.constants import LLM_PROVIDER_API_ERRORS
from sparkth.plugins.compose.conversation_title import extract_title_from_messages, schedule_title_generation
from sparkth.plugins.compose.enums import PlannerModel
from sparkth.plugins.compose.exceptions import ConversationBusy, RAGSearchError
from sparkth.plugins.compose.llm import complete_turn
from sparkth.plugins.compose.messages import get_last_user_text
from sparkth.plugins.compose.models import Conversation
from sparkth.plugins.compose.permissions import CONVERSATION, CONVERSATION_WRITE
from sparkth.plugins.compose.planner import PlannerSetup
from sparkth.plugins.compose.routes.dependencies import get_attachable_document_ids, get_turn_conversation
from sparkth.plugins.compose.routes.utils import (
    get_existing_plan_or_none,
    record_named_tool_denials,
    resolve_tools,
)
from sparkth.plugins.compose.routes.utils.live_turns import (
    claim_conversation,
    release_conversation,
    request_stop,
)
from sparkth.plugins.compose.routes.utils.message_assembly import assemble_provider_messages
from sparkth.plugins.compose.routes.utils.stream_processor import (
    ComposeStreamProcessor,
    streaming_error_message,
)
from sparkth.plugins.compose.routes.utils.stream_schema import get_stream_status_schema
from sparkth.plugins.compose.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from sparkth.plugins.compose.service import ComposeService, get_compose_service
from sparkth.plugins.compose.tools import get_tool_registry
from sparkth.plugins.compose.uploaded_files import add_uploaded_files

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
# union, so the 200 response declares both content types explicitly. The event
# stream's schema covers its status events only, not the reply's text, the final event or errors;
# the frontend's status types are generated from it.
@router.post(
    "/completions",
    response_model=None,
    responses={
        200: {
            "model": ChatCompletionResponse,
            "content": {"text/event-stream": {"schema": get_stream_status_schema()}},
        }
    },
    dependencies=[Depends(CONVERSATION_WRITE.require_for_object(CONVERSATION, get_turn_conversation))],
)
async def compose_completion(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    turn_conversation: Conversation = Depends(get_turn_conversation),
    attachable_document_ids: list[int] = Depends(get_attachable_document_ids),
    session: AsyncSession = Depends(get_async_session),
    service: ComposeService = Depends(get_compose_service),
    llm_service: LLMConfigService = Depends(get_llm_service),
    config: ComposeSettings = Depends(get_compose_settings),
    disabled_plugins: set[str] = Depends(get_disabled_plugins),
) -> Any:
    # The caller runs the turn; the conversation and what it stores belong to the conversation's owner.
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
    allowed_plugins = await get_accessible_scope_object_ids(current_user, PLUGIN_USE, PLUGIN, session)
    # The tool filter and the agent list share the switched-off plugins and the allowed ones.
    agents = enabled_agents(disabled_plugins, allowed_plugins)
    tool_registry = get_tool_registry()
    await record_named_tool_denials(request, tool_registry, disabled_plugins, allowed_plugins)

    conversation, conversation_was_created = await service.get_or_create_conversation(
        session,
        conversation_uuid=conversation_uuid,
        user_id=turn_conversation.user_id,
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
            user_id=turn_conversation.user_id,
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

    if not claim_conversation(str(conversation.uuid)):
        raise ConversationBusy(_("A reply is still being generated in this conversation. Wait for it to finish."))
    # A streamed turn frees the conversation itself, when its stream task ends.
    stream_owns_claim = False
    try:
        if request.document_ids and not attachable_document_ids:
            # The caller may not add documents here, so all of them are dropped and the turn runs without them.
            attachment_analytics.schedule_documents_skipped(
                requested_count=len(set(request.document_ids)),
                skipped_count=len(set(request.document_ids)),
                occurred_at=datetime.now(timezone.utc),
            )
        if attachable_document_ids:
            attached = await service.attach_owned_documents(
                session, conversation_id, attachable_document_ids, turn_conversation.user_id
            )
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
        # Before the turn is stored, so the typed turn of a request refused for its files isn't saved.
        uploaded_files = await add_uploaded_files(conversation.uuid, request.files)
        incoming_messages = await service.add_incoming_messages(session, conversation_id, request.messages)
        for stored in incoming_messages:
            # Instructor turns only: an assistant turn in the request is history the client
            # replayed, and assistant output is counted by compose.completion_served instead.
            if stored.role != "user":
                continue
            turn_analytics.schedule_message_sent(
                message_length=len(stored.content),
                has_attachment=bool(request.files),
                occurred_at=stored.created_at,
            )

        conversation_messages = await service.get_conversation_messages(
            session=session, conversation_id=conversation_id
        )

        # Listed for the planner and its agents, which read the ones a message needs.
        conversation_documents = await service.list_conversation_attachments(
            session=session, conversation_id=conversation_id
        )
        attached_documents = [
            *conversation_documents.ready,
            *(document for document in conversation_documents.unusable if not document.is_deleted),
        ]
        # Document retrieval reads only the documents attached to this conversation.
        bind_readable_document_ids(cast(int, document.id) for document in attached_documents)
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
        # The planner picks who answers. The small model is quicker and cheaper; the reply's model follows the
        # planner's rules more closely.
        planner_model = small_model_for(provider_name) if config.planner_model == PlannerModel.SMALL else model
        planner_llm = get_provider(provider_name, api_key, planner_model, temperature=0).create_llm()

        # The planner hands a message that needs the attached documents to the rag agent, so the route
        # retrieves nothing itself.
        messages, _unresolved_messages = await assemble_provider_messages(
            request,
            conversation_messages,
            [],
            query_text,
            False,
            provider,
            uploaded_files=uploaded_files,
            analytics=turn_analytics,
            listed_documents=attached_documents,
        )

        tools = await resolve_tools(request, tool_registry, disabled_plugins, allowed_plugins)
        planner_setup = PlannerSetup(agents, planner_llm, get_existing_plan_or_none(conversation_messages))

        if request.stream:
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
                user_id=user_id,
                analytics=turn_analytics.attribution,
                turn_id=turn_key,
                max_tool_executions=config.max_tool_executions,
                planner_setup=planner_setup,
            )
            stream_owns_claim = True
            return StreamingResponse(
                # The stream task outlives this response — it writes its analytics after the
                # SSE sentinel — so the holder keeps it referenced until it finishes.
                processor.stream(),
                media_type="text/event-stream",
            )
        else:
            response = await complete_turn(
                messages,
                tools or [],
                provider,
                config.max_tool_executions,
                planner_setup=planner_setup,
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
            )

            # Executions live under metadata: response["tool_calls"] is always None, so reading
            # it would count zero forever.
            response_metadata = response.get("metadata") or {}
            executions = response_metadata.get("tool_executions") or []
            turn_analytics.schedule_completion(
                rag_used=bool(response.get("section_selections")),
                streamed=False,
                executed_tools=executed_tools_from(executions),
                occurred_at=assistant_message.created_at,
                routing=response["routing"],
                agents=response_metadata.get("agents") or [],
            )
            # Nothing records when a step's search returned; the reply's is the nearest moment.
            for section_selection in response.get("section_selections") or []:
                turn_analytics.schedule_rag_search_completed(
                    chunks_found=sum(len(document.sections) for document in section_selection.documents),
                    document_count=len(section_selection.documents),
                    occurred_at=assistant_message.created_at,
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
    finally:
        if not stream_owns_claim:
            release_conversation(str(conversation.uuid))


@router.post("/turns/{turn_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_turn(turn_id: UUID, current_user: User = Depends(get_current_user)) -> None:
    """Ask a streaming turn to stop. 404 covers both an unknown turn and another user's."""
    if not request_stop(str(turn_id), cast(int, current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("No generation is running for this turn."),
        )
