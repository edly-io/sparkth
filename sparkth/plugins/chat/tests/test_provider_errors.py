"""What the completions route does when the chat model's provider fails the call.

Each test drives a real request with the chat model raising a real provider SDK exception, then
reads back what the conversation stored.
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

COMPLETIONS_URL = "/api/v1/chat/completions"
GENERIC_FAILURE = "An error occurred while generating a response. Please try again."

# What langchain-google-genai raises: a wrapped 4xx, a raw 5xx, and an aiohttp transport failure.
GOOGLE_FAILURES = [
    pytest.param(
        ChatGoogleGenerativeAIError("Error calling model 'gemini-2.0-flash' (UNAUTHENTICATED): 401"),
        id="google-4xx",
    ),
    pytest.param(
        google_genai_errors.ServerError(
            503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}
        ),
        id="google-5xx",
    ),
    pytest.param(aiohttp.ClientConnectionError("Connection refused"), id="google-transport"),
]


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
    @pytest.mark.parametrize("failure", GOOGLE_FAILURES)
    async def test_the_turn_fails_with_a_502_and_the_error_is_stored(
        self, client: AsyncClient, current_user: User, session: AsyncSession, failure: Exception
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
        assert response.json() == {"detail": GENERIC_FAILURE}
        stored = await _stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == GENERIC_FAILURE
