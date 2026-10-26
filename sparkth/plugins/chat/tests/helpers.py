"""Helpers shared by the chat plugin's tests: seeded rows, LMS configs, mocked providers and Google's errors."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import aiohttp
import pytest
from google.genai import errors as google_genai_errors
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation, Message

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
