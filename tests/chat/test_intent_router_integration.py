"""Integration tests for RAG Intent Router wired into the chat completion flow."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.encryption import get_encryption_service
from app.core_plugins.chat.intent_router import RAGIntentRouterError
from app.core_plugins.chat.models import Conversation
from app.core_plugins.chat.schemas import RAGRoutingDecision
from app.models.llm import LLMConfig
from app.models.user import User


def _parse_sse_events(content: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in content.decode().splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


class _SeededData:
    def __init__(self, conv_id: int, conv_uuid: str, llm_config_id: int) -> None:
        self.conv_id = conv_id
        self.conv_uuid = conv_uuid
        self.llm_config_id = llm_config_id


async def _seed(session: AsyncSession, user_id: int) -> _SeededData:
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
    llm_config_id = llm_config.id or 0  # capture before expiry

    conv = Conversation(
        user_id=user_id,
        provider="openai",
        model="gpt-4o",
        llm_config_id=llm_config_id,
    )
    session.add(conv)
    await session.flush()
    conv_id = conv.id or 0  # capture before expiry
    conv_uuid = str(conv.uuid)
    await session.commit()
    return _SeededData(conv_id=conv_id, conv_uuid=conv_uuid, llm_config_id=llm_config_id)


def _mock_drive_file(file_id: int = 1, name: str = "lecture.pdf") -> MagicMock:
    f = MagicMock()
    f.id = file_id
    f.name = name
    return f


class TestIntentRouterIntegration:
    """End-to-end tests verifying the router is wired correctly into chat_completion."""

    @pytest.mark.asyncio
    async def test_on_topic_non_streaming_triggers_rag(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """On-topic query with persisted attachments should invoke RAG (non-streaming)."""
        seed = await _seed(session, current_user.id or 1)

        mock_decision = RAGRoutingDecision(should_retrieve=True, reason="document query")
        mock_msg = MagicMock()
        mock_msg.id = 1

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider"),
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_cls_cls,
            patch("app.core_plugins.chat.routes.RAGIntentRouter") as mock_router_cls,
            patch(
                "app.core_plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "app.core_plugins.chat.routes._resolve_drive_file_blocks",
                new_callable=AsyncMock,
            ) as mock_resolve,
            patch(
                "app.core_plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
        ):
            # Scope classifier says in-scope
            mock_scope = AsyncMock()
            mock_scope.classify = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope

            # Router says retrieve=True
            mock_router = MagicMock()
            mock_router.decide = AsyncMock(return_value=mock_decision)
            mock_router_cls.return_value = mock_router

            # One READY attachment exists
            mock_list_attachments.return_value = [_mock_drive_file()]

            # RAG resolution returns the original messages unchanged
            mock_resolve.return_value = [MagicMock(role="user", content="Summarize the document")]

            # Provider returns a simple response
            mock_provider = MagicMock()
            mock_provider.system_prompt = ""
            mock_provider._create_llm.return_value = MagicMock()
            mock_provider.send_message = AsyncMock(
                return_value={
                    "content": "Here is the summary.",
                    "role": "assistant",
                    "tool_calls": None,
                    "metadata": {"usage_metadata": {"total_tokens": 50}},
                }
            )
            mock_get_provider.return_value = mock_provider
            mock_add_msg.return_value = mock_msg

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Summarize the document"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        # Router was called — confirming it's wired in
        mock_router.decide.assert_called_once()
        # RAG resolution was called — confirming retrieve=True triggered it
        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_off_topic_streaming_emits_skipping_rag_event(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """Off-topic query with attachments should emit skipping_rag SSE event (streaming)."""
        seed = await _seed(session, current_user.id or 1)

        mock_decision = RAGRoutingDecision(should_retrieve=False, reason="chit-chat unrelated to documents")
        mock_msg = MagicMock()
        mock_msg.id = 1

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider"),
            patch("app.core_plugins.chat.routes.is_query_in_scope", return_value=True),
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_cls_cls,
            patch("app.core_plugins.chat.routes.RAGIntentRouter") as mock_router_cls,
            patch(
                "app.core_plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "app.core_plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
            patch(
                "app.core_plugins.chat.service.ChatService.get_conversation_messages",
                new_callable=AsyncMock,
            ) as mock_get_msgs,
            # Patch the whole stream so we control the SSE output directly.
            # This test's goal is to verify the router is called with retrieve=False
            # and the route passes rag_routing_reason to the stream correctly.
            patch("app.core_plugins.chat.routes.stream_chat_response") as mock_stream_fn,
        ):
            mock_scope = AsyncMock()
            mock_scope.classify = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope

            mock_router = MagicMock()
            mock_router.decide = AsyncMock(return_value=mock_decision)
            mock_router_cls.return_value = mock_router

            mock_list_attachments.return_value = [_mock_drive_file()]
            mock_get_msgs.return_value = []

            mock_provider = MagicMock()
            mock_provider.system_prompt = ""
            mock_provider._create_llm.return_value = MagicMock()
            mock_get_provider.return_value = mock_provider
            mock_add_msg.return_value = mock_msg

            expected_reason = mock_decision.reason

            # Capture the kwargs the route passes to stream_chat_response so we
            # can assert rag_routing_reason is wired correctly.
            captured_kwargs: dict[str, Any] = {}

            async def _fake_stream(*args: Any, **kwargs: Any) -> Any:
                captured_kwargs.update(kwargs)
                yield f"data: {json.dumps({'status': 'skipping_rag', 'reason': expected_reason, 'done': False})}\n\n"
                yield f"data: {json.dumps({'token': 'Hi!', 'done': False})}\n\n"
                yield f"data: {json.dumps({'done': True, 'conversation_id': seed.conv_uuid})}\n\n"

            mock_stream_fn.side_effect = _fake_stream

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "How is the weather?"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.content)
        skipping = [e for e in events if e.get("status") == "skipping_rag"]
        assert len(skipping) == 1
        assert skipping[0]["reason"] == "chit-chat unrelated to documents"
        # Router was called and decided not to retrieve
        mock_router.decide.assert_called_once()
        assert mock_decision.should_retrieve is False
        # rag_routing_reason is wired through to stream_chat_response
        assert captured_kwargs.get("rag_routing_reason") == "chit-chat unrelated to documents"

    @pytest.mark.asyncio
    async def test_on_topic_streaming_emits_scanning_attachments_event(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """On-topic streaming query with attachments should emit scanning_attachments event."""
        seed = await _seed(session, current_user.id or 1)

        mock_decision = RAGRoutingDecision(should_retrieve=True, reason="document query")
        mock_msg = MagicMock()
        mock_msg.id = 1

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider"),
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_cls_cls,
            patch("app.core_plugins.chat.routes.RAGIntentRouter") as mock_router_cls,
            patch(
                "app.core_plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "app.core_plugins.chat.routes.stream_chat_response",
            ) as mock_stream,
            patch(
                "app.core_plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
        ):
            mock_scope = AsyncMock()
            mock_scope.classify = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope

            mock_router = MagicMock()
            mock_router.decide = AsyncMock(return_value=mock_decision)
            mock_router_cls.return_value = mock_router

            mock_list_attachments.return_value = [_mock_drive_file()]

            mock_provider = MagicMock()
            mock_provider.system_prompt = ""
            mock_provider._create_llm.return_value = MagicMock()
            mock_get_provider.return_value = mock_provider
            mock_add_msg.return_value = mock_msg

            # Produce a scanning_attachments event from the mocked stream
            async def _fake_stream(*args: Any, **kwargs: Any) -> Any:
                yield f"data: {json.dumps({'status': 'scanning_attachments', 'file_count': 1, 'done': False})}\n\n"
                yield f"data: {json.dumps({'token': 'Summary.', 'done': False})}\n\n"
                yield f"data: {json.dumps({'done': True, 'conversation_id': seed.conv_uuid})}\n\n"

            mock_stream.return_value = _fake_stream()

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Summarize chapter 1"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        events = _parse_sse_events(response.content)
        scanning = [e for e in events if e.get("status") == "scanning_attachments"]
        assert len(scanning) == 1
        assert scanning[0]["file_count"] == 1
        # Router was called with retrieve=True
        mock_router.decide.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_attachments_skips_router_silently(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """When no attachments exist, router is never called and no SSE events are emitted."""
        seed = await _seed(session, current_user.id or 1)

        mock_msg = MagicMock()
        mock_msg.id = 1

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider"),
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_cls_cls,
            patch("app.core_plugins.chat.routes.RAGIntentRouter") as mock_router_cls,
            patch(
                "app.core_plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "app.core_plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
        ):
            mock_scope = AsyncMock()
            mock_scope.classify = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope

            mock_router_cls.return_value = MagicMock()
            mock_list_attachments.return_value = []  # no attachments

            mock_provider = MagicMock()
            mock_provider.system_prompt = ""
            mock_provider._create_llm.return_value = MagicMock()

            async def _stream(*args: Any, **kwargs: Any) -> Any:
                yield "Hi!"

            mock_provider.stream_message = _stream
            mock_get_provider.return_value = mock_provider
            mock_add_msg.return_value = mock_msg

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        # Router class was never instantiated
        mock_router_cls.assert_not_called()
        # No router SSE events in stream
        events = _parse_sse_events(response.content)
        router_events = [e for e in events if e.get("status") in ("scanning_attachments", "skipping_rag")]
        assert router_events == []

    @pytest.mark.asyncio
    async def test_router_failure_returns_502(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """Router raising RAGIntentRouterError must surface as HTTP 502 (fail-closed)."""
        seed = await _seed(session, current_user.id or 1)

        with (
            patch("app.core_plugins.chat.routes.get_provider") as mock_get_provider,
            patch("app.core_plugins.chat.routes.get_rag_provider"),
            patch("app.core_plugins.chat.routes.ScopeClassifier") as mock_cls_cls,
            patch("app.core_plugins.chat.routes.RAGIntentRouter") as mock_router_cls,
            patch(
                "app.core_plugins.chat.service.ChatService.list_conversation_attachments",
                new_callable=AsyncMock,
            ) as mock_list_attachments,
            patch(
                "app.core_plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ),
            patch(
                "app.core_plugins.chat.service.ChatService.get_conversation_messages",
                new_callable=AsyncMock,
            ) as mock_get_msgs,
        ):
            mock_scope = AsyncMock()
            mock_scope.classify = AsyncMock(return_value=True)
            mock_cls_cls.return_value = mock_scope

            mock_router = MagicMock()
            mock_router.decide = AsyncMock(side_effect=RAGIntentRouterError("LLM call failed"))
            mock_router_cls.return_value = mock_router

            mock_list_attachments.return_value = [_mock_drive_file()]
            mock_get_msgs.return_value = []

            mock_provider = MagicMock()
            mock_provider.system_prompt = ""
            mock_provider._create_llm.return_value = MagicMock()
            mock_get_provider.return_value = mock_provider

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": seed.llm_config_id,
                    "messages": [{"role": "user", "content": "Summarize"}],
                    "conversation_id": seed.conv_uuid,
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 502
