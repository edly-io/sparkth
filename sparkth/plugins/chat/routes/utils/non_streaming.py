"""Answering a completion turn in one piece, for a request that did not ask to stream."""

from typing import Any, cast

from langchain_core.tools import BaseTool

from sparkth.lib.llm import BaseChatProvider
from sparkth.plugins.chat.analytics import ChatTurnAnalytics, tool_names
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.routes.utils.turn_context import TurnContext
from sparkth.plugins.chat.schemas import ChatCompletionResponse, ChatMessage


async def complete_without_stream(
    provider: BaseChatProvider,
    messages: list[dict[str, Any]],
    tools: list[BaseTool] | None,
    rag_search_required: bool,
    conversation: Conversation,
    turn: TurnContext,
    turn_analytics: ChatTurnAnalytics,
) -> ChatCompletionResponse:
    """Ask the provider for the whole reply, store it, queue ``completion_served`` and return it.

    Tool executions are read from the reply's metadata: ``response["tool_calls"]`` is hard-coded
    to None by every provider, so reading it would count zero forever.
    """
    response = await provider.send_message(
        messages=messages,
        max_tokens=turn.request.max_tokens,
        tools=tools,
    )

    tokens_used = response.get("metadata", {}).get("usage_metadata", {}).get("total_tokens")
    tool_calls = response.get("tool_calls")

    assistant_message = await turn.service.add_message(
        session=turn.session,
        conversation_id=cast(int, conversation.id),
        role="assistant",
        content=response["content"],
        tokens_used=tokens_used,
        metadata=response.get("metadata"),
        message_type="text",
    )

    response_metadata = response.get("metadata") or {}
    executions = response_metadata.get("tool_executions") or []
    turn_analytics.schedule_completion(
        rag_used=rag_search_required,
        streamed=False,
        executed_tools=tool_names(executions),
        occurred_at=assistant_message.created_at,
    )

    return ChatCompletionResponse(
        message=ChatMessage(
            role="assistant",
            content=response["content"],
        ),
        conversation_id=conversation.uuid,
        model=turn.model,
        provider=turn.provider_name,
        tokens_used=tokens_used,
        tool_calls=tool_calls,
        metadata=response.get("metadata", {}),
    )
