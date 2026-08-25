"""Tests for query scope validation (is_query_in_scope in prompt.py)."""

import json
import logging
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
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE, is_query_in_scope
from sparkth.plugins.chat.routes.utils import classify_in_scope, stream_out_of_scope_refusal
from sparkth.plugins.chat.schemas import ChatCompletionResponse, ChatMessage


class TestScopeValidation:
    """Test the is_query_in_scope function against assets/scope_keywords.json."""

    def test_course_creation_queries_are_in_scope(self) -> None:
        assert is_query_in_scope("Create a course on data privacy") is True
        assert is_query_in_scope("Design a lesson outline for climate change") is True
        assert is_query_in_scope("What's the best way to structure a course module?") is True
        assert is_query_in_scope("Create an assessment for my geology course") is True

    def test_general_knowledge_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("What is the capital of France?") is False
        assert is_query_in_scope("Who is the president of the United States?") is False
        assert is_query_in_scope("Where is the Eiffel Tower located?") is False

    def test_code_help_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("Help me write Python code") is False
        assert is_query_in_scope("Can you fix this bug?") is False
        assert is_query_in_scope("Debug my JavaScript code") is False

    def test_personal_advice_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("Can you help me with financial advice?") is False
        assert is_query_in_scope("What's the best legal strategy?") is False

    def test_web_search_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("What is the current weather today?") is False
        assert is_query_in_scope("Get me the latest news on the economy") is False

    def test_teaching_methodology_is_in_scope(self) -> None:
        assert is_query_in_scope("How to teach calculus effectively") is True
        assert is_query_in_scope("What are best practices for instructional design?") is True

    def test_empty_query_defaults_to_in_scope(self) -> None:
        """Empty queries should default to in-scope (let LLM handle)."""
        assert is_query_in_scope("") is True

    def test_queries_with_course_keywords_override_out_of_scope_defaults(self) -> None:
        assert is_query_in_scope("How many students should I include in my course?") is True
        assert is_query_in_scope("Can you help create a curriculum on ethics?") is True

    def test_word_boundary_prevents_substring_collisions(self) -> None:
        """'code' should not match 'barcode'; 'java' should not match 'javascript'."""
        # "barcode" contains "code" as a substring — should NOT be flagged out-of-scope
        # (no in_scope keywords either, so defaults to in-scope for LLM to handle)
        assert is_query_in_scope("Build a barcode reader app") is True
        # "java" as a whole word is out-of-scope; no in_scope keyword present
        assert is_query_in_scope("I need help with Java development") is False

    def test_course_related_query_with_potential_substring_match_is_in_scope(self) -> None:
        """Queries that contain both course keywords and out-of-scope substrings should pass."""
        # "learning objective" (in-scope) wins over partial matches
        assert is_query_in_scope("Write a learning objective for data analysis") is True
        # "curriculum" (in-scope) wins
        assert is_query_in_scope("Who is responsible for curriculum design in K-12?") is True

    def test_translation_requests_reach_the_classifier(self) -> None:
        """ "translate" must not hard-refuse: the keyword layer cannot express the
        system prompt's "unrelated to course content" qualifier, so it over-refuses.
        The LLM classifier downstream handles the genuinely out-of-scope case."""
        assert is_query_in_scope("translate this into Spanish") is True
        assert is_query_in_scope("Can you translate my content to French") is True
        assert is_query_in_scope("translate everything to German") is True
        # Contrast case from the research table: this one already passed before the fix,
        # because the in-scope "outline" short-circuits the out-of-scope check. Kept to
        # pin that the in-scope override still wins.
        assert is_query_in_scope("translate this outline into Spanish") is True

    def test_non_english_query_falls_through_to_the_classifier(self) -> None:
        """A non-English query matches no English keyword either way, so the filter
        returns True and the classifier decides. Pins existing behaviour that nothing
        else asserts — the pre-filter is a fast path, never a non-English refusal."""
        assert is_query_in_scope("crea un curso sobre privacidad de datos") is True
        assert is_query_in_scope("créer un cours sur la protection des données") is True


class TestScopeRefusalLogging:
    """The keyword filter refuses without calling any model, so the log is the only trace.

    Nothing else records this decision: the LLM classifier is short-circuited and the
    chat model is never invoked, so a refusal here is invisible unless it is logged.
    """

    def test_keyword_refusal_logs_the_matched_keywords(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            assert is_query_in_scope("Show me the Python snippet for Acme Corp") is False

        assert "python" in caplog.text.lower()

    def test_keyword_refusal_does_not_log_the_message_text(self, caplog: pytest.LogCaptureFixture) -> None:
        """Only the matched keywords may be logged — the message itself can hold course content."""
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            assert is_query_in_scope("Show me the Python snippet for Acme Corp") is False

        assert "Acme Corp" not in caplog.text
        assert "snippet" not in caplog.text

    def test_keyword_refusal_logs_the_conversation_uuid(self, caplog: pytest.LogCaptureFixture) -> None:
        """Without it a reviewer can only correlate refusals by timestamp, not to a thread."""
        conversation_uuid = uuid4()

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            assert is_query_in_scope("Show me the Python snippet", conversation_uuid) is False

        assert str(conversation_uuid) in caplog.text

    def test_keyword_refusal_before_a_conversation_exists_logs_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """The first message of a new chat is checked before any conversation row exists."""
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            assert is_query_in_scope("Show me the Python snippet") is False

        assert "conversation_uuid=None" in caplog.text

    @pytest.mark.asyncio
    async def test_classify_in_scope_forwards_the_uuid_to_the_keyword_filter(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The keyword filter short-circuits before any model, so no provider is reached here."""
        conversation_uuid = uuid4()

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            in_scope = await classify_in_scope(
                "Show me the Python snippet", "anthropic", "test-key", [], None, conversation_uuid
            )

        assert in_scope is False
        assert str(conversation_uuid) in caplog.text

    @pytest.mark.asyncio
    async def test_classify_in_scope_forwards_the_uuid_to_the_classifier(self) -> None:
        """A query the keyword filter passes must carry the uuid on to the LLM classifier."""
        conversation_uuid = uuid4()

        with patch("sparkth.plugins.chat.routes.utils.ScopeClassifier") as MockClassifier:
            MockClassifier.return_value.classify = AsyncMock(return_value=True)
            await classify_in_scope(
                "Create a course on data privacy", "anthropic", "test-key", [], None, conversation_uuid
            )

        _, kwargs = MockClassifier.return_value.classify.call_args
        assert kwargs["conversation_uuid"] == conversation_uuid

    def test_in_scope_query_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        """A warning per passing message would drown the refusals it exists to surface."""
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.prompt"):
            assert is_query_in_scope("Create a course on data privacy") is True

        assert caplog.text == ""


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
        """Keyword-filtered out-of-scope first message → no conversation in DB."""
        llm_config_id = await _seed_llm_config(session, current_user.id or 1)
        before = await _count_user_conversations(session, current_user.id or 1)

        mock_msg = MagicMock()
        mock_msg.id = 1

        # Subject here is DB record behaviour, not language — the locale is pinned
        # explicitly rather than relying on the ambient default.
        with (
            locale_context("en"),
            patch("sparkth.plugins.chat.routes.completions.get_provider"),
            patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=False),
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
            patch("sparkth.plugins.chat.routes.utils.is_query_in_scope", return_value=False),
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
