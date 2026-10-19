"""Tests for the chat scope gate at the route boundary.

The judgement itself belongs to MessageScopeClassifier and is asserted in test_message_scope.py.
What is left here is what the route does with the outcome. For a refusal: the SSE event it
streams, the response shape it allows, and the DB records it must and must not write. For a
check that could not judge the turn: the 502 and the text the user reads, the error it stores,
and that the chat model is never reached.
"""

import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import httpx
import openai
import pytest
from httpx import AsyncClient
from langchain_openai.chat_models.base import OpenAIRefusalError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n import locale_context
from sparkth.lib.models import User
from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.routes.utils.stream_processor import stream_out_of_scope_refusal
from sparkth.plugins.chat.tests.helpers import (
    GOOGLE_FAILURES,
    classifier_provider,
    seed_conversation,
    seed_llm_config,
    stored_messages,
)
from sparkth.plugins.chat.types import ConversationDocuments

_OPENAI_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
_ANTHROPIC_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_OPENAI_UNREACHABLE = "Could not reach OpenAI. Please check your network connection."
_GENERIC_FAILURE = "An error occurred while generating a response. Please try again."
_ROUTE_LOGGER = "sparkth.plugins.chat.routes.completions"
_OPENAI_REFUSAL = OpenAIRefusalError("I can't help with that.")

# Classifier answers that carry no verdict: one off the schema, one refused by OpenAI's structured output.
_UNJUDGED_ANSWERS = [
    pytest.param(AsyncMock(return_value={"in_scope": "maybe"}), id="schema-misfit"),
    pytest.param(AsyncMock(side_effect=_OPENAI_REFUSAL), id="openai-refusal"),
]

# Provider failures with the text the user reads for each.
_PROVIDER_FAILURES = [
    pytest.param(openai.APIConnectionError(request=_OPENAI_REQUEST), _OPENAI_UNREACHABLE, id="openai-connection"),
    pytest.param(
        openai.APIStatusError("Internal error", response=httpx.Response(500, request=_OPENAI_REQUEST), body=None),
        "OpenAI API error (500). Please try again.",
        id="openai-status",
    ),
    pytest.param(
        anthropic.AuthenticationError(
            "invalid x-api-key", response=httpx.Response(401, request=_ANTHROPIC_REQUEST), body=None
        ),
        "Invalid API key. Please check your Anthropic API key in AI Keys.",
        id="anthropic-key",
    ),
]


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
        llm_config_id = await seed_llm_config(session, current_user.id or 1)

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
        llm_config_id = await seed_llm_config(session, current_user.id or 1)
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


# ── helpers ─────────────────────────────────────────────────────────────────


async def _count_user_conversations(session: AsyncSession, user_id: int) -> int:
    result = await session.exec(
        select(func.count()).select_from(Conversation).where(col(Conversation.user_id) == user_id)
    )
    return result.one()


async def _send(client: AsyncClient, config_id: int, conversation_uuid: str | None, stream: bool) -> httpx.Response:
    """One turn of a new chat (no ``conversation_uuid``) or of an existing one."""
    body: dict[str, Any] = {
        "llm_config_id": config_id,
        "messages": [{"role": "user", "content": "Create a course on data privacy"}],
        "stream": stream,
        "tools": "none",
    }
    if conversation_uuid:
        body["conversation_id"] = conversation_uuid
    return await client.post("/api/v1/chat/completions", json=body)


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
        llm_config_id = await seed_llm_config(session, current_user.id or 1)
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
        llm_config_id = await seed_llm_config(session, current_user.id or 1)

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
                return_value=ConversationDocuments(ready=[], unusable=[]),
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


class TestAFailedScopeCheck:
    """A scope check that cannot judge the turn fails it, and the chat model is never called.

    The classifier's model call raises a real provider SDK exception, the way production fails.
    The route's answer and the stored messages are read back.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stream", [False, True])
    async def test_a_first_message_fails_with_the_provider_text_and_writes_nothing(
        self, client: AsyncClient, current_user: User, session: AsyncSession, stream: bool
    ) -> None:
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        before = await _count_user_conversations(session, user_id)
        failure = openai.APIConnectionError(request=_OPENAI_REQUEST)

        with (
            locale_context("en"),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=classifier_provider(AsyncMock(side_effect=failure)),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, None, stream)

        # Raised before any SSE starts, so a streamed request gets the same JSON error.
        assert response.status_code == 502
        assert response.json() == {"detail": _OPENAI_UNREACHABLE}
        assert await _count_user_conversations(session, user_id) == before
        chat_provider.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("stream", [False, True])
    @pytest.mark.parametrize(("failure", "detail"), _PROVIDER_FAILURES)
    async def test_a_later_turn_stores_one_error_after_the_message(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        failure: Exception,
        detail: str,
        stream: bool,
    ) -> None:
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        conversation_uuid = await seed_conversation(session, user_id)

        with (
            locale_context("en"),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=classifier_provider(AsyncMock(side_effect=failure)),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, conversation_uuid, stream)

        assert response.status_code == 502
        assert response.json() == {"detail": detail}
        stored = await stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == detail
        chat_provider.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("failure", "detail"), GOOGLE_FAILURES)
    async def test_a_google_failure_fails_the_turn_with_the_google_text(
        self, client: AsyncClient, current_user: User, session: AsyncSession, failure: Exception, detail: str
    ) -> None:
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        before = await _count_user_conversations(session, user_id)

        with (
            locale_context("en"),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=classifier_provider(AsyncMock(side_effect=failure)),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, None, False)

        assert response.status_code == 502
        assert response.json() == {"detail": detail}
        assert await _count_user_conversations(session, user_id) == before
        chat_provider.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ainvoke", _UNJUDGED_ANSWERS)
    async def test_a_first_message_whose_answer_does_not_fit_fails_with_the_generic_text(
        self, client: AsyncClient, current_user: User, session: AsyncSession, ainvoke: AsyncMock
    ) -> None:
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        before = await _count_user_conversations(session, user_id)

        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.classifiers.base.get_provider", return_value=classifier_provider(ainvoke)),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, None, False)

        assert response.status_code == 502
        assert response.json() == {"detail": _GENERIC_FAILURE}
        assert await _count_user_conversations(session, user_id) == before
        chat_provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_later_turn_the_classifier_refuses_stores_the_generic_error(
        self, client: AsyncClient, current_user: User, session: AsyncSession
    ) -> None:
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        conversation_uuid = await seed_conversation(session, user_id)

        with (
            locale_context("en"),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=classifier_provider(AsyncMock(side_effect=_OPENAI_REFUSAL)),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, conversation_uuid, False)

        assert response.status_code == 502
        assert response.json() == {"detail": _GENERIC_FAILURE}
        stored = await stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == _GENERIC_FAILURE
        chat_provider.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_later_turn_whose_answer_does_not_fit_logs_no_content(
        self,
        client: AsyncClient,
        current_user: User,
        session: AsyncSession,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A rejected answer can echo the message, which may hold course content."""
        user_id = current_user.id or 1
        config_id = await seed_llm_config(session, user_id)
        conversation_uuid = await seed_conversation(session, user_id)

        with (
            locale_context("en"),
            caplog.at_level(logging.ERROR, logger=_ROUTE_LOGGER),
            patch(
                "sparkth.plugins.chat.classifiers.base.get_provider",
                return_value=classifier_provider(AsyncMock(return_value={"in_scope": "Week 3 confidential syllabus"})),
            ),
            patch("sparkth.plugins.chat.routes.completions.get_provider") as chat_provider,
        ):
            response = await _send(client, config_id, conversation_uuid, False)

        assert response.status_code == 502
        stored = await stored_messages(session, conversation_uuid)
        assert [(m.role, m.is_error) for m in stored] == [("user", False), ("assistant", True)]
        assert stored[-1].content == _GENERIC_FAILURE
        assert "ClassifierError" in caplog.text
        assert "confidential syllabus" not in caplog.text
        chat_provider.assert_not_called()
