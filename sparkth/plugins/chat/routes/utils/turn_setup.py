"""Recording what a completion turn brings into its conversation, before the model is asked."""

from datetime import datetime, timezone
from typing import cast

from sparkth.plugins.chat.analytics import ChatAttachmentAnalytics, ChatTurnAnalytics
from sparkth.plugins.chat.conversation_title import schedule_title_generation
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.routes.utils.turn_context import TurnContext


async def record_incoming_turn(
    conversation: Conversation, conversation_was_created: bool, turn: TurnContext
) -> tuple[ChatTurnAnalytics, ChatAttachmentAnalytics]:
    """Record what the turn brings into ``conversation`` and return the analytics surfaces it used.

    A just-created conversation gets its title and ``conversation_started`` queued first; then the
    request's documents are attached and its messages stored, each with its analytics.
    """
    conversation_id = cast(int, conversation.id)
    turn_analytics = ChatTurnAnalytics(
        background_tasks=turn.background_tasks,
        conversation_id=str(conversation.uuid),
        provider=turn.provider_name,
        model=turn.model,
        actor_id=str(turn.user_id),
    )
    attachment_analytics = ChatAttachmentAnalytics(
        background_tasks=turn.background_tasks,
        conversation_id=str(conversation.uuid),
        actor_id=str(turn.user_id),
    )
    if conversation_was_created:
        _schedule_new_conversation(conversation, turn, turn_analytics)
    await _record_document_attachments(conversation_id, turn, attachment_analytics)
    await _record_incoming_messages(conversation_id, turn, turn_analytics)
    return turn_analytics, attachment_analytics


def _schedule_new_conversation(
    conversation: Conversation, turn: TurnContext, turn_analytics: ChatTurnAnalytics
) -> None:
    """Queue a just-created conversation's title generation, then its ``conversation_started`` event.

    The event is queued after the title task, never before: Starlette runs the background queue
    as a plain sequential loop with no per-task isolation, and analytics emits propagate their
    failures by design, so an emit queued first would let an analytics outage cost the
    conversation its title. The event is timed by the row, because the task runs only after the
    response completes, which for a streamed turn is after the whole stream.
    """
    schedule_title_generation(
        turn.background_tasks,
        turn.service,
        conversation_id=cast(int, conversation.id),
        user_id=turn.user_id,
        messages=turn.request.messages,
        provider_name=turn.provider_name,
        api_key=turn.api_key,
        model=turn.model,
        config=turn.config,
    )
    turn_analytics.schedule_conversation_started(occurred_at=conversation.created_at)


async def _record_document_attachments(
    conversation_id: int, turn: TurnContext, attachment_analytics: ChatAttachmentAnalytics
) -> None:
    """Attach the request's owned documents to the conversation and queue their analytics.

    Skipped documents get an event of their own: the reply says nothing about them, so it is the
    only record that the turn was not what the instructor asked for. Nothing records that moment,
    so it is stamped here.
    """
    if not turn.request.document_ids:
        return
    attached = await turn.service.attach_owned_documents(
        turn.session, conversation_id, turn.request.document_ids, turn.user_id
    )
    for attachment in attached.created:
        attachment_analytics.schedule_document_attached(
            document_id=attachment.document_id,
            source="completion_request",
            occurred_at=attachment.attached_at,
        )
    if attached.skipped_count:
        attachment_analytics.schedule_documents_skipped(
            requested_count=attached.requested_count,
            skipped_count=attached.skipped_count,
            occurred_at=datetime.now(timezone.utc),
        )


async def _record_incoming_messages(conversation_id: int, turn: TurnContext, turn_analytics: ChatTurnAnalytics) -> None:
    """Store the request's messages and queue ``message_sent`` for each instructor turn among them.

    An assistant turn in the request is history the client replayed; assistant output is counted
    by ``chat.completion_served`` instead.
    """
    incoming_messages = await turn.service.add_incoming_messages(turn.session, conversation_id, turn.request.messages)
    for stored in incoming_messages:
        if stored.role != "user":
            continue
        turn_analytics.schedule_message_sent(
            message_length=len(stored.content),
            has_attachment=stored.message_type == "attachment",
            occurred_at=stored.created_at,
        )
