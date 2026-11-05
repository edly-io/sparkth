"""Helpers shared by the Compose plugin's tests: seeded rows, LMS configs, mocked providers and Google's errors."""

from collections.abc import AsyncGenerator, Callable, Iterator, Sequence
from itertools import repeat
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import aiohttp
import pytest
from google.genai import errors as google_genai_errors
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from pydantic import Field
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.compose.hooks import Agent
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.llm import small_model_for
from sparkth.lib.models import LLMConfig
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import ScriptedChatModel
from sparkth.plugins.compose.models import Conversation, Message

GOOGLE_INVALID_KEY = "Invalid API key. Please check your Google API key in AI Keys."
GOOGLE_UNREACHABLE = "Could not reach Google. Please check your network connection."
GOOGLE_OVERLOADED = "Google API error (503). Please try again."

OPENEDX_CONFIG = {
    "lms_url": "https://lms.example.com",
    "studio_url": "https://studio.example.com",
    "lms_username": "edx-author-7731",
    "lms_password": "edx-pass-9d4c",
}
CANVAS_CONFIG = {"api_url": "https://canvas.example.com", "api_key": "token-abc123"}

# Where the stream processor looks up the function that streams a turn; tests patch a scripted
# turn in here to stand in for the model.
STREAM_TURN = "sparkth.plugins.compose.routes.utils.stream_processor.stream_turn"


async def replay_turn(
    events: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    tools: Sequence[Any],
    provider: Any,
    max_tool_executions: int,
    *,
    agents: Sequence[Agent],
    planner_llm: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stand in for ``stream_turn`` with a turn that streams ``events``.

    Bind the events with ``functools.partial(replay_turn, events)`` and patch the result in at
    :data:`STREAM_TURN`.
    """
    for event in events:
        yield event


class RecordingChatModel(ScriptedChatModel):
    """A scripted chat model that keeps the messages of every call it gets in ``seen``."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def answering_model(content: str, total_tokens: int | None = None) -> RecordingChatModel:
    """A chat model that answers every call with ``content``, reporting ``total_tokens`` when given."""
    usage = (
        {"input_tokens": 0, "output_tokens": total_tokens, "total_tokens": total_tokens}
        if total_tokens is not None
        else None
    )
    return RecordingChatModel(messages=repeat(AIMessage(content=content, usage_metadata=usage)))


def _raising(failure: Exception) -> Iterator[AIMessage]:
    raise failure
    yield AIMessage(content="never")


def failing_model(failure: Exception) -> ScriptedChatModel:
    """A chat model whose first call raises ``failure``."""
    return ScriptedChatModel(messages=_raising(failure))


def planner_model(reply: AIMessage) -> ScriptedChatModel:
    """A planner's model answering every message with ``reply``, whole: the fake drops tool calls when it streams."""
    return ScriptedChatModel(messages=repeat(reply), disable_streaming=True)


def hand_off(agent: Agent) -> AIMessage:
    """A planner reply handing the message to ``agent``."""
    return AIMessage("", tool_calls=[{"name": agent.name, "args": {"request": "Go ahead."}, "id": "hand_off"}])


def planner_answering(reply: AIMessage, agent: Agent) -> dict[str, Any]:
    """The ``agents`` and ``planner_llm`` of a turn offering ``agent``, whose planner answers every message
    with ``reply``."""
    return {"agents": [agent], "planner_llm": planner_model(reply)}


def handing_off_to(agent: Agent) -> dict[str, Any]:
    """The ``agents`` and ``planner_llm`` of a turn whose planner hands every message to ``agent``."""
    return planner_answering(hand_off(agent), agent)


def routing_to(provider: Any, agent: Agent) -> Callable[..., Any]:
    """Stand in for the route's ``get_provider``: the planner's small model hands every message to
    ``agent``, and every other model is ``provider``'s."""
    planner = MagicMock()
    planner.create_llm.return_value = planner_model(hand_off(agent))

    def get_provider(provider_name: str, api_key: str, model: str, **kwargs: Any) -> Any:
        return planner if model == small_model_for(provider_name) else provider

    return get_provider


async def seed_llm_config(session: AsyncSession, user_id: int) -> int:
    """An active OpenAI key for ``user_id``, committed, returning its id."""
    enc = get_encryption_service(get_settings().ENCRYPTION_KEY)
    config = LLMConfig(
        user_id=user_id,
        name="test-cfg",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(config)
    await session.flush()
    config_id = config.id or 0
    await session.commit()
    return config_id


async def seed_conversation(session: AsyncSession, user_id: int) -> str:
    """An empty conversation for ``user_id``, committed, returning its uuid."""
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o")
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_uuid


async def stored_messages(session: AsyncSession, conversation_uuid: str) -> list[Message]:
    """The conversation's messages, oldest first, read back from the database."""
    conversation = (
        await session.exec(select(Conversation).where(col(Conversation.uuid) == UUID(conversation_uuid)))
    ).one()
    result = await session.exec(
        select(Message).where(col(Message.conversation_id) == conversation.id).order_by(col(Message.id))
    )
    return list(result.all())


def classifier_provider(ainvoke: AsyncMock) -> MagicMock:
    """A provider whose classifier chain answers, or fails, through ``ainvoke``."""
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(ainvoke=ainvoke)
    provider = MagicMock()
    provider.create_llm.return_value = llm
    return provider


def google_client_error(code: int, status: str, reason: str | None = None) -> google_genai_errors.ClientError:
    """A 4xx as Google's SDK raises it, with an ErrorInfo detail when ``reason`` is given."""
    details = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}] if reason else []
    return google_genai_errors.ClientError(
        code, {"error": {"code": code, "message": "Request failed.", "status": status, "details": details}}
    )


def wrapped_google_error(cause: google_genai_errors.APIError) -> ChatGoogleGenerativeAIError:
    """What langchain-google-genai raises from a non-streamed call: its own error, Google's as the cause."""
    error = ChatGoogleGenerativeAIError(f"Error calling model 'gemini-2.0-flash' ({cause.status}): {cause}")
    error.__cause__ = cause
    return error


# Google reports a bad key as a 400 whose ErrorInfo reason is API_KEY_INVALID.
GOOGLE_KEY_INVALID = google_client_error(400, "INVALID_ARGUMENT", "API_KEY_INVALID")
GOOGLE_OVERLOADED_ERROR = google_genai_errors.ServerError(
    503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}
)

# What langchain-google-genai raises, with the text the user reads for each: a wrapped 4xx, a raw
# 5xx, and an aiohttp transport failure.
GOOGLE_FAILURES = [
    pytest.param(wrapped_google_error(GOOGLE_KEY_INVALID), GOOGLE_INVALID_KEY, id="google-bad-key"),
    pytest.param(GOOGLE_OVERLOADED_ERROR, GOOGLE_OVERLOADED, id="google-5xx"),
    pytest.param(aiohttp.ClientConnectionError("Connection refused"), GOOGLE_UNREACHABLE, id="google-transport"),
]
