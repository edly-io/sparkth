"""Tests for GET /conversations/{conversation_id}/last-message endpoint."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.config import get_chat_settings
from app.core_plugins.chat.models import Conversation, Message
from app.core_plugins.chat.service import ChatService, get_chat_service
from app.llm.service import get_llm_service
from app.main import app


class TestGetLastMessage:
    @pytest.fixture(autouse=True)
    def _override_chat_deps(self, client: httpx.AsyncClient) -> None:  # noqa: PT004
        mock_config = MagicMock()
        mock_config.max_tool_executions = 50
        mock_config.title_max_length = 60

        mock_llm_service = MagicMock()

        app.dependency_overrides[get_chat_settings] = lambda: mock_config
        app.dependency_overrides[get_chat_service] = lambda: ChatService()
        app.dependency_overrides[get_llm_service] = lambda: mock_llm_service

    async def test_returns_null_when_no_messages(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/chat/conversations/{conv.uuid}/last-message")
        assert response.status_code == 200
        assert response.json() is None

    async def test_returns_last_message(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = conv.id
        assert conv_id is not None
        conv_uuid = conv.uuid  # capture before second commit expires the object

        msg1 = Message(conversation_id=conv_id, role="user", content="hello")
        msg2 = Message(conversation_id=conv_id, role="assistant", content="world")
        session.add(msg1)
        session.add(msg2)
        await session.commit()
        await session.refresh(msg2)
        msg2_id = msg2.id

        response = await client.get(f"/api/v1/chat/conversations/{conv_uuid}/last-message")
        assert response.status_code == 200
        body = response.json()
        assert body is not None
        assert body["role"] == "assistant"
        assert body["content"] == "world"
        assert body["id"] == msg2_id

    async def test_returns_last_message_by_created_at_order(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        """Last message is the most recently created one."""
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = conv.id
        assert conv_id is not None
        conv_uuid = conv.uuid

        now = datetime.now(timezone.utc)
        msg1 = Message(conversation_id=conv_id, role="user", content="earlier", created_at=now - timedelta(seconds=10))
        msg2 = Message(conversation_id=conv_id, role="assistant", content="later", created_at=now)
        session.add(msg1)
        session.add(msg2)
        await session.commit()

        response = await client.get(f"/api/v1/chat/conversations/{conv_uuid}/last-message")
        assert response.status_code == 200
        body = response.json()
        assert body["content"] == "later"

    async def test_returns_404_for_unknown_uuid(self, client: httpx.AsyncClient, current_user: MagicMock) -> None:
        response = await client.get(f"/api/v1/chat/conversations/{uuid4()}/last-message")
        assert response.status_code == 404

    async def test_returns_404_for_wrong_user(
        self, client: httpx.AsyncClient, current_user: MagicMock, session: AsyncSession
    ) -> None:
        conv = Conversation(user_id=99999, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/chat/conversations/{conv.uuid}/last-message")
        assert response.status_code == 404

    async def test_returns_422_for_non_uuid(self, client: httpx.AsyncClient, current_user: MagicMock) -> None:
        response = await client.get("/api/v1/chat/conversations/not-a-uuid/last-message")
        assert response.status_code == 422
