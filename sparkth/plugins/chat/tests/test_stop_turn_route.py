"""The stop route reaches only the caller's own live turn."""

import uuid
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.routes.utils.live_turns import register_turn, release_turn, request_stop


@pytest.mark.asyncio
async def test_stopping_a_live_turn_returns_204(client: AsyncClient, current_user: User) -> None:
    stop_requested = register_turn("11111111-1111-4111-8111-111111111111", cast(int, current_user.id))
    try:
        response = await client.post("/api/v1/chat/turns/11111111-1111-4111-8111-111111111111/stop")
        assert response.status_code == 204
        assert stop_requested.is_set()
    finally:
        release_turn("11111111-1111-4111-8111-111111111111", cast(int, current_user.id))


@pytest.mark.asyncio
async def test_stopping_an_unknown_turn_returns_404(client: AsyncClient, current_user: User) -> None:
    response = await client.post("/api/v1/chat/turns/22222222-2222-4222-8222-222222222222/stop")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stopping_another_users_turn_returns_404(client: AsyncClient, current_user: User) -> None:
    other_user_id = cast(int, current_user.id) + 1000
    stop_requested = register_turn("33333333-3333-4333-8333-333333333333", other_user_id)
    try:
        response = await client.post("/api/v1/chat/turns/33333333-3333-4333-8333-333333333333/stop")
        assert response.status_code == 404
        assert not stop_requested.is_set()
    finally:
        release_turn("33333333-3333-4333-8333-333333333333", other_user_id)


async def _seed_llm_config_and_conversation(session: AsyncSession, user_id: int) -> tuple[int, str]:
    """Seed a usable LLM config and an existing conversation for a streaming completion request."""
    settings = get_settings()
    enc = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    llm_config = LLMConfig(
        user_id=user_id,
        name="test-cfg",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(llm_config)
    await session.flush()
    llm_config_id = llm_config.id or 0

    conversation = Conversation(user_id=user_id, provider="openai", model="gpt-4o", llm_config_id=llm_config_id)
    session.add(conversation)
    await session.flush()
    conversation_uuid = str(conversation.uuid)
    await session.commit()
    return llm_config_id, conversation_uuid


class TestTurnNotLeakedWhenStreamNeverStarts:
    """A turn that never streams must leave nothing behind in the registry.

    Registering and releasing both happen inside the task the stream spawns, so a request
    that fails before that task exists — or a response whose body is never read — has
    nothing to release.
    """

    @pytest.mark.asyncio
    async def test_a_construction_failure_leaves_no_registered_turn(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        user_id = cast(int, current_user.id)
        llm_config_id, conversation_uuid = await _seed_llm_config_and_conversation(session, user_id)
        turn_id = str(uuid.uuid4())

        with (
            patch("sparkth.plugins.chat.routes.completions.get_provider") as mock_get_provider,
            patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as mock_cls_cls,
            patch(
                "sparkth.plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "sparkth.plugins.chat.routes.completions.ChatStreamProcessor",
                side_effect=TypeError("simulated construction failure"),
            ),
        ):
            mock_scope = AsyncMock()
            mock_scope.in_scope = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope
            mock_list_attachments.return_value = []

            mock_provider = AsyncMock()
            mock_provider.system_prompt = ""
            mock_get_provider.return_value = mock_provider

            with pytest.raises(TypeError, match="simulated construction failure"):
                await client.post(
                    "/api/v1/chat/completions",
                    json={
                        "llm_config_id": llm_config_id,
                        "messages": [{"role": "user", "content": "Hello"}],
                        "conversation_id": conversation_uuid,
                        "stream": True,
                        "tools": "none",
                        "turn_id": turn_id,
                    },
                )

        # request_stop returning False proves the id is not in the registry — a leaked turn
        # would still be there and this would return True instead.
        assert request_stop(turn_id, user_id) is False
