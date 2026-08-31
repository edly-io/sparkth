"""Tests for the refusal the chat scope gate produces, at the route boundary.

The judgement itself belongs to MessageScopeClassifier and is asserted in
test_message_scope.py. What is left here is what the route does with a refusal: the SSE
event it streams, the response shape it allows, and the DB records it must and must not
write.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n import locale_context
from sparkth.lib.encryption import get_encryption_service
from sparkth.lib.models import LLMConfig, User
from sparkth.lib.settings import get_settings
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE
from sparkth.plugins.chat.routes.utils import stream_out_of_scope_refusal
from sparkth.plugins.chat.schemas import ChatCompletionResponse, ChatMessage


class TestStreamOutOfScopeRefusal:
    """Test the stream_out_of_scope_refusal SSE generator."""

    @pytest.mark.asyncio
    async def test_emits_single_done_event_with_refusal_content(self) -> None:
        """stream_out_of_scope_refusal yields exactly one SSE done event.

        Subject here is the event shape, not the language it renders in — the
        locale is pinned explicitly rather than relying on the ambient default.
        """
        with locale_context("en"):
            events = []
            async for chunk in stream_out_of_scope_refusal():
                events.append(chunk)

            assert len(events) == 1
            assert events[0].startswith("data: ")
            payload = json.loads(events[0].removeprefix("data: ").strip())
            assert payload["done"] is True
            assert payload["content"] == REFUSAL_MESSAGE


class TestThePreflightCheckSeesTheWholeTurn:
    """The first message of a new chat is judged before any DB write.

    Nothing has been persisted at that point, so the request itself is the only place the
    turn's attachments can come from. Leaving them out would hand the classifier an empty
    query with no sign of what the user actually sent.
    """

    @pytest.mark.asyncio
    async def test_attachment_names_from_the_request_reach_the_classifier(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)

        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as MockClassifier,
        ):
            MockClassifier.return_value.in_scope = AsyncMock(return_value=False)
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "document",
                                    "source": {"type": "base64", "media_type": "application/pdf", "data": ""},
                                }
                            ],
                            "attachment": {"name": "syllabus.pdf", "size": 1024},
                        }
                    ],
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        query, _history, attachments, _uuid = MockClassifier.return_value.in_scope.await_args.args
        assert query == ""
        assert attachments == ["syllabus.pdf"]


class TestAnExistingConversationSeesTheWholeTurnToo:
    """A locally uploaded file never becomes a Document row.

    The conversation's attachments come from the database, which only knows documents that were
    ingested — a file uploaded with the message is base64 content and has no row. So the request is
    the only place its name exists, on this path as much as on the pre-flight one, and without it
    the classifier is handed an empty message to judge.
    """

    @pytest.mark.asyncio
    async def test_a_locally_uploaded_file_reaches_the_classifier_by_name(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)
        conversation = Conversation(
            user_id=current_user.id or 1,
            provider="openai",
            model="gpt-4o",
            llm_config_id=llm_config_id,
        )
        session.add(conversation)
        await session.flush()
        conversation_uuid = str(conversation.uuid)
        await session.commit()

        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.routes.completions.MessageScopeClassifier") as MockClassifier,
            patch("sparkth.plugins.chat.service.ChatService.add_message", new_callable=AsyncMock),
        ):
            MockClassifier.return_value.in_scope = AsyncMock(return_value=False)
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "conversation_id": conversation_uuid,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "document",
                                    "source": {"type": "base64", "media_type": "application/pdf", "data": ""},
                                }
                            ],
                            "attachment": {"name": "syllabus.pdf", "size": 1024},
                        }
                    ],
                    "stream": False,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        query, _history, attachments, _uuid = MockClassifier.return_value.in_scope.await_args.args
        assert query == ""
        assert attachments == ["syllabus.pdf"]


class TestChatCompletionResponseSchema:
    """ChatCompletionResponse must accept a null conversation_id."""

    def test_conversation_id_can_be_none(self) -> None:
        resp = ChatCompletionResponse(
            message=ChatMessage(role="assistant", content="sorry"),
            conversation_id=None,
            model="gpt-4o",
            provider="openai",
        )
        assert resp.conversation_id is None

    def test_conversation_id_can_be_uuid(self) -> None:
        uid = uuid4()
        resp = ChatCompletionResponse(
            message=ChatMessage(role="assistant", content="hello"),
            conversation_id=uid,
            model="gpt-4o",
            provider="openai",
        )
        assert resp.conversation_id == uid


# ── helpers ─────────────────────────────────────────────────────────────────


async def _seed_llm_config(session: AsyncSession, user_id: int) -> int:
    """Create an LLMConfig in DB and return its id."""
    settings = get_settings()
    enc = get_encryption_service(settings.LLM_ENCRYPTION_KEY)
    cfg = LLMConfig(
        user_id=user_id,
        name="test-cfg-scope",
        provider="openai",
        model="gpt-4o",
        encrypted_key=enc.encrypt("sk-test"),
        masked_key="sk-***",
        is_active=True,
    )
    session.add(cfg)
    await session.flush()
    llm_config_id = cfg.id or 0
    await session.commit()
    return llm_config_id


async def _count_user_conversations(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        sa_select(func.count()).where(Conversation.user_id == user_id)  # type: ignore[arg-type]
    )
    return result.scalar_one()  # type: ignore[no-any-return]


class TestOutOfScopeConversationCreation:
    """Out-of-scope first messages must not create any DB record."""

    @pytest.mark.asyncio
    async def test_out_of_scope_new_message_creates_no_conversation(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """Out-of-scope first message → no conversation in DB."""
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)
        before = await _count_user_conversations(session, current_user.id or 1)

        mock_msg = MagicMock()
        mock_msg.id = 1

        # Subject here is DB record behaviour, not language — the locale is pinned
        # explicitly rather than relying on the ambient default.
        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.routes.completions.get_provider"),
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=MagicMock(in_scope=AsyncMock(return_value=False)),
            ),
            patch(
                "sparkth.plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
                return_value=mock_msg,
            ),
        ):
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        assert any(e.get("done") and e.get("content") == REFUSAL_MESSAGE for e in events)

        after = await _count_user_conversations(session, current_user.id or 1)
        assert after == before, f"Expected no new conversation, got {after - before} new"

    @pytest.mark.asyncio
    async def test_out_of_scope_existing_conversation_still_saves_refusal(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
    ) -> None:
        """Out-of-scope message in an EXISTING conversation must still save refusal to DB."""
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)

        # Create a conversation first
        conv = Conversation(
            user_id=current_user.id or 1,
            provider="openai",
            model="gpt-4o",
            llm_config_id=llm_config_id,
        )
        session.add(conv)
        await session.flush()
        conv_uuid = str(conv.uuid)
        await session.commit()

        # Subject here is that a message got persisted, not the language it was
        # persisted in — the locale is pinned explicitly rather than relying on the
        # ambient default.
        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.routes.completions.get_provider"),
            patch(
                "sparkth.plugins.chat.routes.completions.MessageScopeClassifier",
                return_value=MagicMock(in_scope=AsyncMock(return_value=False)),
            ),
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
            patch(
                "sparkth.plugins.chat.service.ChatService.add_message",
                new_callable=AsyncMock,
            ) as mock_add_msg,
        ):
            mock_msg = MagicMock()
            mock_msg.id = 99
            mock_add_msg.return_value = mock_msg

            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "llm_config_id": llm_config_id,
                    "messages": [{"role": "user", "content": "what is 2+2?"}],
                    "conversation_id": conv_uuid,
                    "stream": True,
                    "tools": "none",
                },
            )

        assert response.status_code == 200
        # add_message must have been called at least once with role="assistant"
        all_calls = mock_add_msg.call_args_list
        assistant_calls = [c for c in all_calls if c.kwargs.get("role") == "assistant"]
        assert len(assistant_calls) == 1
        assert assistant_calls[0].kwargs["content"] == REFUSAL_MESSAGE
