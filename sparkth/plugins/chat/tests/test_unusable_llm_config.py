"""The three ways a request can name an LLM config it cannot use.

Each is one status and one sentence the user can act on, and each persists that sentence
against the conversation so a reload still shows it — which is why the handler answers them
itself instead of leaving them to the exception registry.

The suite reached this route only on its happy path, so these three answers were unasserted.
They are pinned here so a restructure of the handler has something to be checked against.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.llm import (
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    get_llm_service,
)
from sparkth.main import app
from sparkth.plugins.chat.config import get_chat_settings
from sparkth.plugins.chat.models import Conversation, Message
from sparkth.plugins.chat.service import ChatService, get_chat_service

# The exception the resolve raises, the status it becomes, and a fragment of the sentence the
# user is given. The fragment rather than the whole string: this asserts which message was
# chosen, not the copy, which the catalogs own. Instances rather than classes because the three
# constructors do not agree on their arguments.
UNUSABLE_CONFIG = [
    pytest.param(LLMConfigNotFoundError(1, 1), 404, "No AI Key found", id="not-found"),
    pytest.param(LLMConfigModelNotSetError("model is not set"), 422, "has no model configured", id="model-not-set"),
    pytest.param(LLMConfigInactiveError(), 409, "deactivated", id="inactive"),
]


class TestUnusableConfigIsAnswered:
    @pytest.fixture
    def raising_llm_service(self) -> MagicMock:
        """An LLM service whose resolve is the first thing the handler calls, and fails."""
        service = MagicMock()
        service.resolve = AsyncMock()
        return service

    @pytest.fixture(autouse=True)
    def _override_chat_deps(self, client: httpx.AsyncClient, raising_llm_service: MagicMock) -> None:  # noqa: PT004
        settings = MagicMock()
        settings.max_tool_executions = 50
        settings.title_max_length = 60

        app.dependency_overrides[get_chat_settings] = lambda: settings
        app.dependency_overrides[get_chat_service] = lambda: ChatService()
        app.dependency_overrides[get_llm_service] = lambda: raising_llm_service

    @pytest.mark.parametrize(("error", "expected_status", "fragment"), UNUSABLE_CONFIG)
    async def test_each_failure_gets_its_own_status_and_message(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        raising_llm_service: MagicMock,
        error: Exception,
        expected_status: int,
        fragment: str,
    ) -> None:
        raising_llm_service.resolve.side_effect = error

        response = await client.post(
            "/api/v1/chat/completions",
            json={"llm_config_id": 1, "messages": [{"role": "user", "content": "hello"}]},
        )

        assert response.status_code == expected_status
        assert fragment in response.json()["detail"]

    @pytest.mark.parametrize(("error", "expected_status", "fragment"), UNUSABLE_CONFIG)
    async def test_the_message_is_persisted_against_the_conversation(
        self,
        client: httpx.AsyncClient,
        current_user: MagicMock,
        session: AsyncSession,
        raising_llm_service: MagicMock,
        error: Exception,
        expected_status: int,
        fragment: str,
    ) -> None:
        """A reload shows the failure, so it is written before the status is raised."""
        conversation = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conversation)
        # Committed, not flushed: the request runs in its own session and rolls back what only
        # this one has seen.
        await session.commit()
        await session.refresh(conversation)
        conversation_id, conversation_uuid = conversation.id, conversation.uuid

        raising_llm_service.resolve.side_effect = error

        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "llm_config_id": 1,
                "conversation_id": str(conversation_uuid),
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert response.status_code == expected_status

        stored = (
            await session.exec(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(col(Message.created_at).desc())
            )
        ).first()
        assert stored is not None
        assert stored.is_error is True
        assert stored.role == "assistant"
        assert fragment in stored.content
