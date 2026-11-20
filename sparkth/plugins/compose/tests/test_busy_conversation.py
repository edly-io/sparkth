"""A conversation runs one turn at a time: a second turn is refused until the first ends."""

from datetime import datetime, timezone
from functools import partial
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.compose.hooks import Agent
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.models import User
from sparkth.plugins.compose.models import Conversation, ConversationAttachment
from sparkth.plugins.compose.routes.utils.live_turns import claim_conversation, release_conversation
from sparkth.plugins.compose.tests.helpers import (
    STREAM_TURN,
    answering_model,
    hand_off,
    planning,
    replay_turn,
    seed_conversation,
    seed_llm_config,
    stored_messages,
)
from sparkth.plugins.compose.types import ConversationDocuments


async def _get_conversation_id(session: AsyncSession, conversation_uuid: str) -> int:
    conversation = (
        await session.exec(select(Conversation).where(col(Conversation.uuid) == UUID(conversation_uuid)))
    ).one()
    return cast(int, conversation.id)


def _build_completion_request(llm_config_id: int, conversation_uuid: str) -> dict[str, object]:
    return {
        "llm_config_id": llm_config_id,
        "messages": [{"role": "user", "content": "Hello"}],
        "conversation_id": conversation_uuid,
        "stream": True,
        "tools": "none",
    }


@pytest.mark.asyncio
async def test_a_turn_on_a_busy_conversation_is_refused_and_stores_nothing(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    llm_config_id = await seed_llm_config(session, cast(int, current_user.id))
    conversation_uuid = await seed_conversation(session, cast(int, current_user.id))
    claim_conversation(conversation_uuid)
    try:
        response = await client.post(
            "/api/v1/compose/completions", json=_build_completion_request(llm_config_id, conversation_uuid)
        )
    finally:
        release_conversation(conversation_uuid)

    assert response.status_code == 409
    assert await stored_messages(session, conversation_uuid) == []


@pytest.mark.asyncio
async def test_a_turn_on_a_busy_conversation_attaches_none_of_its_documents(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    user_id = cast(int, current_user.id)
    llm_config_id = await seed_llm_config(session, user_id)
    conversation_uuid = await seed_conversation(session, user_id)
    conversation_id = await _get_conversation_id(session, conversation_uuid)
    document = Document(user_id=user_id, name="notes.pdf", status=DocumentStatus.READY)
    session.add(document)
    await session.commit()
    request = _build_completion_request(llm_config_id, conversation_uuid) | {"document_ids": [document.id]}

    claim_conversation(conversation_uuid)
    try:
        response = await client.post("/api/v1/compose/completions", json=request)
    finally:
        release_conversation(conversation_uuid)

    assert response.status_code == 409
    attached = await session.exec(
        select(ConversationAttachment).where(ConversationAttachment.conversation_id == conversation_id)
    )
    assert attached.all() == []


@pytest.mark.asyncio
async def test_a_streamed_turn_frees_its_conversation_for_the_next(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    llm_config_id = await seed_llm_config(session, cast(int, current_user.id))
    conversation_uuid = await seed_conversation(session, cast(int, current_user.id))
    stored_message = MagicMock(id=1, created_at=datetime.now(timezone.utc))

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
        patch(STREAM_TURN, partial(replay_turn, [{"type": "token", "content": "Hi!"}])),
        patch(
            "sparkth.plugins.compose.service.ComposeService.list_conversation_attachments",
            new_callable=AsyncMock,
            return_value=ConversationDocuments(ready=[], unusable=[]),
        ),
        patch(
            "sparkth.plugins.compose.service.ComposeService.add_message",
            new_callable=AsyncMock,
            return_value=stored_message,
        ),
    ):
        mock_get_provider.return_value = MagicMock(system_prompt="")
        request = _build_completion_request(llm_config_id, conversation_uuid)
        first = await client.post("/api/v1/compose/completions", json=request)
        second = await client.post("/api/v1/compose/completions", json=request)

    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_a_turn_answered_in_one_response_frees_its_conversation_for_the_next(
    client: AsyncClient, current_user: User, session: AsyncSession, stub_agent: Agent
) -> None:
    llm_config_id = await seed_llm_config(session, cast(int, current_user.id))
    conversation_uuid = await seed_conversation(session, cast(int, current_user.id))
    provider = MagicMock()
    provider.create_llm.return_value = answering_model("Sure.")
    request = _build_completion_request(llm_config_id, conversation_uuid) | {"stream": False}

    with patch(
        "sparkth.plugins.compose.routes.completions.get_provider",
        side_effect=planning(provider, hand_off(stub_agent)),
    ):
        first = await client.post("/api/v1/compose/completions", json=request)
        second = await client.post("/api/v1/compose/completions", json=request)

    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_a_turn_that_fails_before_streaming_frees_its_conversation(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    llm_config_id = await seed_llm_config(session, cast(int, current_user.id))
    conversation_uuid = await seed_conversation(session, cast(int, current_user.id))

    with (
        patch("sparkth.plugins.compose.routes.completions.get_provider") as mock_get_provider,
        patch(
            "sparkth.plugins.compose.service.ComposeService.list_conversation_attachments",
            new_callable=AsyncMock,
            return_value=ConversationDocuments(ready=[], unusable=[]),
        ),
        patch(
            "sparkth.plugins.compose.routes.completions.ComposeStreamProcessor",
            side_effect=TypeError("simulated construction failure"),
        ),
    ):
        mock_get_provider.return_value = AsyncMock(system_prompt="")
        with pytest.raises(TypeError, match="simulated construction failure"):
            await client.post(
                "/api/v1/compose/completions", json=_build_completion_request(llm_config_id, conversation_uuid)
            )

    try:
        assert claim_conversation(conversation_uuid) is True
    finally:
        release_conversation(conversation_uuid)
