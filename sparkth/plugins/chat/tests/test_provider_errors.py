"""What the user reads when a provider fails the call, and what the completions route stores.

The wording tests hand ``streaming_error_message`` the exceptions Google's SDK raises. The route
tests drive a real request with the chat model raising one, then read back what the conversation
stored.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import aiohttp
import pytest
from google.genai import errors as google_genai_errors
from httpx import AsyncClient
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n import locale_context
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation, Message
from sparkth.plugins.chat.routes.utils.stream_processor import streaming_error_message

COMPLETIONS_URL = "/api/v1/chat/completions"
GENERIC_FAILURE = "An error occurred while generating a response. Please try again."
GOOGLE_INVALID_KEY = "Invalid API key. Please check your Google API key in AI Keys."
GOOGLE_UNREACHABLE = "Could not reach Google. Please check your network connection."
GOOGLE_OVERLOADED = "Google API error (503). Please try again."


def _google_client_error(code: int, status: str, reason: str | None = None) -> google_genai_errors.ClientError:
    """A 4xx as Google's SDK raises it, with an ErrorInfo detail when ``reason`` is given."""
    details = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}] if reason else []
    return google_genai_errors.ClientError(
        code, {"error": {"code": code, "message": "Request failed.", "status": status, "details": details}}
    )


def _wrapped(cause: google_genai_errors.APIError) -> ChatGoogleGenerativeAIError:
    """What langchain-google-genai raises from a non-streamed call: its own error, Google's as the cause."""
    error = ChatGoogleGenerativeAIError(f"Error calling model 'gemini-2.0-flash' ({cause.status}): {cause}")
    error.__cause__ = cause
    return error


# Google reports a bad key as a 400 whose ErrorInfo reason is API_KEY_INVALID.
_KEY_INVALID = _google_client_error(400, "INVALID_ARGUMENT", "API_KEY_INVALID")
_OVERLOADED = google_genai_errors.ServerError(
    503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}
)

# What langchain-google-genai raises, with the text the user reads for each: a wrapped 4xx, a raw
# 5xx, and an aiohttp transport failure.
GOOGLE_FAILURES = [
    pytest.param(_wrapped(_KEY_INVALID), GOOGLE_INVALID_KEY, id="google-bad-key"),
    pytest.param(_OVERLOADED, GOOGLE_OVERLOADED, id="google-5xx"),
    pytest.param(aiohttp.ClientConnectionError("Connection refused"), GOOGLE_UNREACHABLE, id="google-transport"),
]


class TestGoogleErrorWording:
    """A Google failure tells the user what went wrong, wrapped or raw."""

    @pytest.mark.parametrize(
        ("failure", "detail"),
        [
            pytest.param(_wrapped(_KEY_INVALID), GOOGLE_INVALID_KEY, id="bad-key-wrapped"),
            # A streamed call raises Google's error unwrapped.
            pytest.param(_KEY_INVALID, GOOGLE_INVALID_KEY, id="bad-key-raw"),
            pytest.param(_google_client_error(401, "UNAUTHENTICATED"), GOOGLE_INVALID_KEY, id="unauthenticated"),
            pytest.param(
                _wrapped(_google_client_error(403, "PERMISSION_DENIED")),
                "Your Google API key does not have permission to use this model.",
                id="permission",
            ),
            pytest.param(
                _wrapped(_google_client_error(429, "RESOURCE_EXHAUSTED")),
                "Google API rate limit reached. Please wait a moment and try again.",
                id="rate-limit",
            ),
            pytest.param(
                _wrapped(_google_client_error(400, "INVALID_ARGUMENT")),
                "The request was rejected by Google. Please try a different message.",
                id="rejected",
            ),
            pytest.param(_OVERLOADED, GOOGLE_OVERLOADED, id="server-error"),
            pytest.param(aiohttp.ClientConnectionError("Connection refused"), GOOGLE_UNREACHABLE, id="unreachable"),
            # Raised for a local failure too, with no Google error underneath.
            pytest.param(ChatGoogleGenerativeAIError("Unknown error"), GENERIC_FAILURE, id="no-google-cause"),
        ],
    )
    def test_the_user_reads(self, failure: Exception, detail: str) -> None:
        with locale_context("en"):
            assert streaming_error_message(failure) == detail


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    enc = get_encryption_service(get_settings().LLM_ENCRYPTION_KEY)
    config = LLMConfig(
        user_id=user_id,
        name="test-cfg-provider-errors",
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


async def _seed_conversation(session: AsyncSession, user_id: int) -> str:
    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o")
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return conversation_uuid


async def _stored_messages(session: AsyncSession, conversation_uuid: str) -> list[Message]:
    """The conversation's messages, oldest first, read back from the database."""
    conversation = (
        await session.exec(select(Conversation).where(col(Conversation.uuid) == UUID(conversation_uuid)))
    ).one()
    result = await session.exec(
        select(Message).where(col(Message.conversation_id) == conversation.id).order_by(col(Message.id))
    )
    return list(result.all())


def _classifier_provider(ainvoke: AsyncMock) -> MagicMock:
    """A provider whose classifier chain answers, or fails, through ``ainvoke``."""
    llm = MagicMock()
    llm.with_structured_output.return_value = MagicMock(ainvoke=ainvoke)
    provider = MagicMock()
    provider.create_llm.return_value = llm
    return provider


def _chat_provider(failure: Exception) -> MagicMock:
    provider = MagicMock()
    provider.model = "gpt-4o"
    provider.system_prompt = ""
    provider.send_message = AsyncMock(side_effect=failure)
    return provider


class TestAGoogleChatModelFailure:
    """A Google SDK error from the chat model fails the turn like any other provider error."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("failure", "detail"), GOOGLE_FAILURES)
    async def test_the_turn_fails_with_a_502_and_the_error_is_stored(
        self, client: AsyncClient, current_user: User, session: AsyncSession, failure: Exception, detail: str
    ) -> None:
        user_id = current_user.id or 1
        config_id = await _seed_llm_config(session, user_id)
        conversation_uuid = await _seed_conversation(session, user_id)
        body: dict[str, Any] = {
            "llm_config_id": config_id,
            "conversation_id": conversation_uuid,
            "messages": [{"role": "user", "content": "Create a course on data privacy"}],
            "stream": False,
            "tools": "none",
        }

        with (
            locale_context("en"),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=_classifier_provider(AsyncMock(return_value={"in_scope": True})),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_chat_provider(failure)),
        ):
            response = await client.post(COMPLETIONS_URL, json=body)

        assert response.status_code == 502
        assert response.json() == {"detail": detail}
        stored = await _stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == detail
