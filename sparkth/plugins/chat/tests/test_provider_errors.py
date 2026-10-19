"""What the user reads when a provider fails the call, and what the completions route stores.

The wording tests hand ``streaming_error_message`` the exceptions Google's SDK raises. The route
tests drive a real request with the chat model raising one, then read back what the conversation
stored.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from httpx import AsyncClient
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n import locale_context
from sparkth.lib.models import User
from sparkth.plugins.chat.routes.utils.stream_processor import streaming_error_message
from sparkth.plugins.chat.tests.helpers import (
    GOOGLE_FAILURES,
    GOOGLE_INVALID_KEY,
    GOOGLE_KEY_INVALID,
    GOOGLE_OVERLOADED,
    GOOGLE_OVERLOADED_ERROR,
    GOOGLE_UNREACHABLE,
    classifier_provider,
    google_client_error,
    seed_conversation,
    seed_llm_config,
    stored_messages,
    wrapped_google_error,
)

COMPLETIONS_URL = "/api/v1/chat/completions"
GENERIC_FAILURE = "An error occurred while generating a response. Please try again."


class TestGoogleErrorWording:
    """A Google failure tells the user what went wrong, wrapped or raw."""

    @pytest.mark.parametrize(
        ("failure", "detail"),
        [
            pytest.param(wrapped_google_error(GOOGLE_KEY_INVALID), GOOGLE_INVALID_KEY, id="bad-key-wrapped"),
            # A streamed call raises Google's error unwrapped.
            pytest.param(GOOGLE_KEY_INVALID, GOOGLE_INVALID_KEY, id="bad-key-raw"),
            pytest.param(google_client_error(401, "UNAUTHENTICATED"), GOOGLE_INVALID_KEY, id="unauthenticated"),
            pytest.param(
                wrapped_google_error(google_client_error(403, "PERMISSION_DENIED")),
                "Your Google API key does not have permission to use this model.",
                id="permission",
            ),
            pytest.param(
                wrapped_google_error(google_client_error(429, "RESOURCE_EXHAUSTED")),
                "Google API rate limit reached. Please wait a moment and try again.",
                id="rate-limit",
            ),
            pytest.param(
                wrapped_google_error(google_client_error(400, "INVALID_ARGUMENT")),
                "The request was rejected by Google. Please try a different message.",
                id="rejected",
            ),
            pytest.param(GOOGLE_OVERLOADED_ERROR, GOOGLE_OVERLOADED, id="server-error"),
            pytest.param(aiohttp.ClientConnectionError("Connection refused"), GOOGLE_UNREACHABLE, id="unreachable"),
            # Raised for a local failure too, with no Google error underneath.
            pytest.param(ChatGoogleGenerativeAIError("Unknown error"), GENERIC_FAILURE, id="no-google-cause"),
        ],
    )
    def test_the_user_reads(self, failure: Exception, detail: str) -> None:
        with locale_context("en"):
            assert streaming_error_message(failure) == detail


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
        config_id = await seed_llm_config(session, user_id)
        conversation_uuid = await seed_conversation(session, user_id)
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
                return_value=classifier_provider(AsyncMock(return_value={"in_scope": True})),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider", return_value=_chat_provider(failure)),
        ):
            response = await client.post(COMPLETIONS_URL, json=body)

        assert response.status_code == 502
        assert response.json() == {"detail": detail}
        stored = await stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == detail
