"""The resolved preferred language reaches the provider's system prompt.

Template rendering is covered by test_prompt.py; this file pins the wiring — that
chat_completion resolves the signed-in user's stored preference, and that it re-resolves
per request, so a preference changed mid-conversation applies from the next turn.

The mock stack mirrors test_intent_router_integration.py, which drives the same route.
"""

import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation


class _Seeded:
    def __init__(self, llm_config_id: int, conversation_uuid: str) -> None:
        self.llm_config_id = llm_config_id
        self.conversation_uuid = conversation_uuid


async def _seed(session: AsyncSession, user_id: int) -> _Seeded:
    """An active LLM config plus an existing conversation.

    Posting into an existing conversation keeps the assertion on the language and off
    the new-conversation path, which also schedules title generation.
    """
    settings = get_settings()
    encryption = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    llm_config = LLMConfig(
        user_id=user_id,
        name="test-cfg-language",
        provider="openai",
        model="gpt-4o",
        encrypted_key=encryption.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(llm_config)
    await session.flush()
    llm_config_id = llm_config.id or 0  # capture before expiry

    conversation = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        llm_config_id=llm_config_id,
    )
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return _Seeded(llm_config_id, conversation_uuid)


async def _fake_stream() -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'done': True})}\n\n"


async def _system_prompt_for_one_request(client: AsyncClient, seed: _Seeded) -> str:
    """Send one completion request; return the system prompt handed to the provider."""
    with (
        patch("sparkth.plugins.chat.routes.completions.get_provider") as mock_get_provider,
        patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=True),
        patch("sparkth.plugins.chat.routes.utils.ScopeClassifier") as mock_classifier_cls,
        patch(
            "sparkth.plugins.chat.routes.completions.resolve_rag_intent",
            new_callable=AsyncMock,
            return_value=(False, None),
        ),
        patch("sparkth.plugins.chat.service.ChatService.add_message", new_callable=AsyncMock) as mock_add_message,
        patch(
            "sparkth.plugins.chat.service.ChatService.get_conversation_messages",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "sparkth.plugins.chat.service.ChatService.list_conversation_attachments",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("sparkth.plugins.chat.routes.completions.ChatStreamProcessor") as mock_processor_cls,
    ):
        mock_classifier = MagicMock()
        mock_classifier.classify = AsyncMock(return_value=True)
        mock_classifier_cls.return_value = mock_classifier

        mock_message = MagicMock()
        mock_message.id = 1
        mock_add_message.return_value = mock_message

        mock_provider = MagicMock()
        mock_provider.system_prompt = ""
        mock_provider.create_llm.return_value = MagicMock()
        mock_get_provider.return_value = mock_provider

        mock_processor = MagicMock()
        mock_processor.stream.return_value = _fake_stream()
        mock_processor_cls.return_value = mock_processor

        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "llm_config_id": seed.llm_config_id,
                "messages": [{"role": "user", "content": "Create a course on data privacy"}],
                "conversation_id": seed.conversation_uuid,
                "stream": True,
                "tools": "none",
            },
        )

    assert response.status_code == 200
    return str(mock_get_provider.call_args.kwargs["system_prompt"])


class TestCompletionLanguageWiring:
    """The `current_user` fixture overrides the auth dependency with an in-memory User,
    so setting `.language` on it is the whole of "the user chose this language" — the
    row is never read back from the database."""

    async def test_stored_preference_reaches_the_system_prompt(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        seed = await _seed(session, current_user.id or 1)
        current_user.language = "es"

        prompt = await _system_prompt_for_one_request(client, seed)

        assert SUPPORTED_LANGUAGES["es"].name in prompt

    async def test_unset_preference_falls_back_to_the_platform_default(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        seed = await _seed(session, current_user.id or 1)
        current_user.language = None

        prompt = await _system_prompt_for_one_request(client, seed)

        assert SUPPORTED_LANGUAGES[get_settings().DEFAULT_LANGUAGE].name in prompt

    async def test_changing_the_preference_applies_to_the_next_turn(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """The prompt is rebuilt per request, so no conversation-level pinning exists
        and none should be added: the next turn simply switches language."""
        seed = await _seed(session, current_user.id or 1)

        current_user.language = "es"
        first = await _system_prompt_for_one_request(client, seed)
        current_user.language = "fr"
        second = await _system_prompt_for_one_request(client, seed)

        assert SUPPORTED_LANGUAGES["es"].name in first
        assert SUPPORTED_LANGUAGES["fr"].name in second
        assert SUPPORTED_LANGUAGES["es"].name not in second
