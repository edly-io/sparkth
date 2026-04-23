"""
Tests for the conversation UUID feature (PR #220 / Issue #190):
  - Conversation model auto-generates UUIDv7
  - ChatService.get_conversation_by_uuid lookups
  - Schemas expose UUID instead of int IDs
  - API routes accept/return UUIDs for conversations
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ConversationResponse,
)

# ===========================================================================
# Conversation model — UUID field
# ===========================================================================


class TestConversationModelUUID:
    def test_uuid_auto_generated_on_instantiation(self) -> None:
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert isinstance(conv.uuid, UUID)

    def test_uuid_is_unique_across_instances(self) -> None:
        conv_a = Conversation(user_id=1, provider="openai", model="gpt-4o")
        conv_b = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert conv_a.uuid != conv_b.uuid

    def test_uuid_can_be_set_explicitly(self) -> None:
        explicit = uuid7()
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o", uuid=explicit)
        assert conv.uuid == explicit

    def test_uuid_is_version_7(self) -> None:
        conv = Conversation(user_id=1, provider="openai", model="gpt-4o")
        assert conv.uuid.version == 7


# ===========================================================================
# ChatService.get_conversation_by_uuid
# ===========================================================================


class TestGetConversationByUUID:
    async def test_returns_conversation_matching_uuid_and_user(self, session: "AsyncSession") -> None:
        from app.core_plugins.chat.service import ChatService

        svc = ChatService(encryption_service=MagicMock(), cache_service=MagicMock())
        conv = Conversation(user_id=42, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        result = await svc.get_conversation_by_uuid(session, uuid=conv.uuid, user_id=42)
        assert result is not None
        assert result.id == conv.id
        assert result.uuid == conv.uuid

    async def test_returns_none_for_wrong_user(self, session: "AsyncSession") -> None:
        from app.core_plugins.chat.service import ChatService

        svc = ChatService(encryption_service=MagicMock(), cache_service=MagicMock())
        conv = Conversation(user_id=42, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        result = await svc.get_conversation_by_uuid(session, uuid=conv.uuid, user_id=999)
        assert result is None

    async def test_returns_none_for_nonexistent_uuid(self, session: "AsyncSession") -> None:
        from app.core_plugins.chat.service import ChatService

        svc = ChatService(encryption_service=MagicMock(), cache_service=MagicMock())
        result = await svc.get_conversation_by_uuid(session, uuid=uuid4(), user_id=1)
        assert result is None


# ===========================================================================
# Schema — UUID types
# ===========================================================================


class TestConversationUUIDSchemas:
    def test_chat_completion_request_accepts_uuid_conversation_id(self) -> None:
        uid = uuid7()
        req = ChatCompletionRequest(
            provider="openai",
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            conversation_id=uid,
        )
        assert req.conversation_id == uid

    def test_chat_completion_request_accepts_none_conversation_id(self) -> None:
        req = ChatCompletionRequest(
            provider="openai",
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
        )
        assert req.conversation_id is None

    def test_chat_completion_request_accepts_uuid_string(self) -> None:
        uid = uuid7()
        req = ChatCompletionRequest(
            provider="openai",
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
            conversation_id=str(uid),  # type: ignore[arg-type]
        )
        assert req.conversation_id == uid

    def test_chat_completion_request_rejects_integer_conversation_id(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatCompletionRequest(
                provider="openai",
                model="gpt-4o",
                messages=[ChatMessage(role="user", content="hello")],
                conversation_id=123,  # type: ignore[arg-type]
            )

    def test_chat_completion_response_conversation_id_is_uuid(self) -> None:
        uid = uuid7()
        resp = ChatCompletionResponse(
            message=ChatMessage(role="assistant", content="hi"),
            conversation_id=uid,
            model="gpt-4o",
            provider="openai",
        )
        assert isinstance(resp.conversation_id, UUID)
        assert resp.conversation_id == uid

    def test_conversation_response_id_is_uuid(self) -> None:
        from datetime import datetime, timezone

        uid = uuid7()
        now = datetime.now(timezone.utc)
        resp = ConversationResponse(
            id=uid,
            provider="openai",
            model="gpt-4o",
            title=None,
            total_tokens_used=0,
            total_cost=0.0,
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(resp.id, UUID)
        assert resp.id == uid


# ===========================================================================
# API routes — conversations expose UUIDs
# ===========================================================================


class TestConversationUUIDRoutes:
    @pytest.fixture(autouse=True)
    def _override_chat_deps(self, client: httpx.AsyncClient) -> None:  # noqa: PT004
        """Override chat dependencies so route tests don't need real env vars."""
        from app.core_plugins.chat.routes import get_chat_service, get_chat_system_config
        from app.core_plugins.chat.service import ChatService
        from app.main import app

        mock_config = MagicMock()
        mock_config.max_tool_executions = 50
        mock_config.title_max_length = 60

        mock_service = ChatService(
            encryption_service=MagicMock(),
            cache_service=MagicMock(),
        )

        app.dependency_overrides[get_chat_system_config] = lambda: mock_config
        app.dependency_overrides[get_chat_service] = lambda: mock_service

    async def test_list_conversations_returns_uuids(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get("/api/v1/chat/conversations")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1

        conv_data = body["conversations"][0]
        returned_id = conv_data["id"]
        # Should be a valid UUID string, not an integer
        parsed = UUID(returned_id)
        assert parsed == conv.uuid

    async def test_get_conversation_by_uuid(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=current_user.id, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/chat/conversations/{conv.uuid}")
        assert response.status_code == 200
        body = response.json()
        assert UUID(body["id"]) == conv.uuid
        assert body["provider"] == "openai"
        assert body["model"] == "gpt-4o"

    async def test_get_conversation_by_uuid_not_found(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        fake_uuid = uuid4()
        response = await client.get(f"/api/v1/chat/conversations/{fake_uuid}")
        assert response.status_code == 404

    async def test_get_conversation_by_integer_returns_422(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.get("/api/v1/chat/conversations/123")
        assert response.status_code == 422

    async def test_get_conversation_wrong_user_returns_404(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        conv = Conversation(user_id=99999, provider="openai", model="gpt-4o")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)

        response = await client.get(f"/api/v1/chat/conversations/{conv.uuid}")
        assert response.status_code == 404

    async def test_completions_returns_uuid_conversation_id(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        from app.core_plugins.chat.models import Message, ProviderAPIKey

        key = ProviderAPIKey(
            user_id=current_user.id,
            provider="openai",
            encrypted_key="enc",
            masked_key="****",
            is_active=True,
        )
        session.add(key)
        await session.commit()

        mock_response: dict[str, Any] = {
            "content": "Hello!",
            "role": "assistant",
            "model": "gpt-4o",
            "tool_calls": None,
            "metadata": {},
        }

        mock_message = Message(id=1, conversation_id=1, role="assistant", content="Hello!")

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider") as mock_get_rag_provider,
            patch("app.core_plugins.chat.routes.generate_conversation_title"),
            patch("app.core_plugins.chat.service.ChatService.get_api_key", new_callable=AsyncMock) as mock_get_key,
            patch("app.core_plugins.chat.service.ChatService.add_message", new_callable=AsyncMock) as mock_add_message,
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_classifier_cls,
        ):
            mock_get_rag_provider.return_value = MagicMock()
            mock_classifier = AsyncMock()
            mock_classifier.classify = AsyncMock(return_value=True)
            mock_classifier_cls.return_value = mock_classifier
            mock_provider = AsyncMock()
            mock_provider.send_message = AsyncMock(return_value=mock_response)
            mock_get_provider.return_value = mock_provider
            mock_get_key.return_value = "sk-fake-key"
            mock_add_message.return_value = mock_message

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hi"}],
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        body = response.json()
        # conversation_id should be a valid UUID
        UUID(body["conversation_id"])

    async def test_completions_with_existing_uuid_conversation(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession"
    ) -> None:
        from app.core_plugins.chat.models import Message, ProviderAPIKey

        key = ProviderAPIKey(
            user_id=current_user.id,
            provider="openai",
            encrypted_key="enc",
            masked_key="****",
            is_active=True,
        )
        session.add(key)
        await session.flush()

        conv = Conversation(
            user_id=current_user.id,
            api_key_id=key.id,
            provider="openai",
            model="gpt-4o",
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_uuid = conv.uuid

        mock_response: dict[str, Any] = {
            "content": "Hello again!",
            "role": "assistant",
            "model": "gpt-4o",
            "tool_calls": None,
            "metadata": {},
        }

        mock_message = Message(id=1, conversation_id=conv.id, role="assistant", content="Hello again!")  # type: ignore[arg-type]

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider") as mock_get_rag_provider,
            patch("app.core_plugins.chat.service.ChatService.get_api_key", new_callable=AsyncMock) as mock_get_key,
            patch("app.core_plugins.chat.service.ChatService.add_message", new_callable=AsyncMock) as mock_add_message,
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_classifier_cls,
        ):
            mock_get_rag_provider.return_value = MagicMock()
            mock_classifier = AsyncMock()
            mock_classifier.classify = AsyncMock(return_value=True)
            mock_classifier_cls.return_value = mock_classifier
            mock_provider = AsyncMock()
            mock_provider.send_message = AsyncMock(return_value=mock_response)
            mock_get_provider.return_value = mock_provider
            mock_get_key.return_value = "sk-fake-key"
            mock_add_message.return_value = mock_message

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hello again"}],
                    "conversation_id": str(conv_uuid),
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert UUID(body["conversation_id"]) == conv_uuid

    async def test_completions_with_nonexistent_uuid_returns_404(
        self, client: "httpx.AsyncClient", current_user: MagicMock, session: "AsyncSession", mock_rag_provider: MagicMock
    ) -> None:
        with patch("app.core_plugins.chat.service.ChatService.get_api_key", new_callable=AsyncMock) as mock_get_key:
            mock_get_key.return_value = "sk-fake-key"

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "hi"}],
                    "conversation_id": str(uuid4()),
                    "tools": "none",
                },
            )

        assert response.status_code == 404

    async def test_completions_with_integer_conversation_id_returns_422(
        self, client: "httpx.AsyncClient", current_user: MagicMock, mock_rag_provider: MagicMock
    ) -> None:
        response = await client.post(
            "/api/v1/chat/completions",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "hi"}],
                "conversation_id": 123,
            },
        )
        assert response.status_code == 422
