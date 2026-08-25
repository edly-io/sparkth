"""Unit tests for the chat scope classifier."""

import logging
from typing import Literal, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.exceptions import LangChainException

from sparkth.plugins.chat.classifier import HistoryTurn, ScopeClassifier, _ScopeResult


def _build_classifier(provider: str = "anthropic") -> tuple["ScopeClassifier", AsyncMock]:
    """Construct a ScopeClassifier with a mocked LangChain client.

    Returns (classifier, mock_chain) where mock_chain.ainvoke controls responses.
    """
    chat_cls = {
        "anthropic": "sparkth.plugins.chat.classifier.ChatAnthropic",
        "openai": "sparkth.plugins.chat.classifier.ChatOpenAI",
        "google": "sparkth.plugins.chat.classifier.ChatGoogleGenerativeAI",
    }[provider]

    with patch(chat_cls) as MockChat:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = AsyncMock()
        MockChat.return_value = mock_llm
        classifier = ScopeClassifier(provider_name=provider, api_key="test-key")

    # Replace chain with a fresh AsyncMock after construction so tests control responses
    mock_chain = AsyncMock()
    classifier._chain = mock_chain
    return classifier, mock_chain


class TestScopeClassifierInit:
    def test_raises_for_unknown_provider(self) -> None:
        with pytest.raises(ValueError, match="Unsupported provider"):
            ScopeClassifier(provider_name="unknownprovider", api_key="key")

    def test_anthropic_uses_haiku_model(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatAnthropic") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="anthropic", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "claude-haiku-4-5"

    def test_openai_uses_mini_model(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatOpenAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="openai", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "gpt-4o-mini"

    def test_google_uses_flash_model(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatGoogleGenerativeAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="google", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "gemini-2.0-flash"

    def test_temperature_is_zero_for_determinism(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatAnthropic") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="anthropic", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("temperature") == 0

    def test_temperature_is_zero_for_openai(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatOpenAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="openai", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("temperature") == 0

    def test_temperature_is_zero_for_google(self) -> None:
        with patch("sparkth.plugins.chat.classifier.ChatGoogleGenerativeAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="google", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("temperature") == 0


class TestScopeClassifierClassify:
    @pytest.mark.asyncio
    async def test_empty_query_skips_llm_and_returns_true(self) -> None:
        classifier, mock_chain = _build_classifier()
        result = await classifier.classify("")
        mock_chain.ainvoke.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_whitespace_query_skips_llm_and_returns_true(self) -> None:
        classifier, mock_chain = _build_classifier()
        result = await classifier.classify("   ")
        mock_chain.ainvoke.assert_not_called()
        assert result is True

    @pytest.mark.asyncio
    async def test_in_scope_returns_true(self) -> None:
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        assert await classifier.classify("Create a course on data privacy") is True

    @pytest.mark.asyncio
    async def test_out_of_scope_returns_false(self) -> None:
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=False))
        assert await classifier.classify("What is the capital of France?") is False

    @pytest.mark.asyncio
    async def test_out_of_scope_is_logged_with_the_deciding_model(self, caplog: pytest.LogCaptureFixture) -> None:
        """A refusal is a model judgement on truncated history — the log is where that is auditable."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=False))

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.classifier"):
            assert await classifier.classify("What is the capital of France?") is False

        assert "claude-haiku-4-5" in caplog.text

    @pytest.mark.asyncio
    async def test_out_of_scope_log_reports_how_much_history_was_available(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Only the last _MAX_HISTORY_TURNS reach the model, so the total is what shows truncation."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=False))
        history: list[HistoryTurn] = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(9)
        ]

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.classifier"):
            assert await classifier.classify("no", history=history) is False

        assert "9" in caplog.text

    @pytest.mark.asyncio
    async def test_out_of_scope_log_includes_the_conversation_uuid(self, caplog: pytest.LogCaptureFixture) -> None:
        """Ties the refusal to the thread a user reports, which they identify by the chat URL."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=False))
        conversation_uuid = uuid4()

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.classifier"):
            assert await classifier.classify("no", conversation_uuid=conversation_uuid) is False

        assert str(conversation_uuid) in caplog.text

    @pytest.mark.asyncio
    async def test_out_of_scope_log_omits_the_message_text(self, caplog: pytest.LogCaptureFixture) -> None:
        """The refused message can hold course content; only its length may be logged."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=False))

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.classifier"):
            assert await classifier.classify("Acme Corp onboarding secrets") is False

        assert "Acme Corp" not in caplog.text

    @pytest.mark.asyncio
    async def test_in_scope_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))

        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.classifier"):
            assert await classifier.classify("Create a course on data privacy") is True

        assert caplog.text == ""

    @pytest.mark.asyncio
    async def test_langchain_error_fails_open(self) -> None:
        """On any LangChain error, classifier returns True (fail open)."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(side_effect=LangChainException("timeout"))
        assert await classifier.classify("some query") is True

    @pytest.mark.asyncio
    async def test_sends_system_and_human_messages(self) -> None:
        """Chain receives [SystemMessage, HumanMessage(query)] in that order."""
        from langchain_core.messages import HumanMessage, SystemMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        await classifier.classify("design a quiz")
        (msgs,), _ = mock_chain.ainvoke.call_args
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "design a quiz"

    @pytest.mark.asyncio
    async def test_history_user_role_maps_to_human_message(self) -> None:
        from langchain_core.messages import HumanMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        history: list[HistoryTurn] = [{"role": "user", "content": "prior user turn"}]
        await classifier.classify("follow-up", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        # msgs[0] is SystemMessage; msgs[1] is history turn; msgs[2] is current query
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "prior user turn"

    @pytest.mark.asyncio
    async def test_history_assistant_role_maps_to_ai_message(self) -> None:
        from langchain_core.messages import AIMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        history: list[HistoryTurn] = [{"role": "assistant", "content": "prior assistant turn"}]
        await classifier.classify("follow-up", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        assert isinstance(msgs[1], AIMessage)
        assert msgs[1].content == "prior assistant turn"

    @pytest.mark.asyncio
    async def test_history_unknown_role_is_skipped(self) -> None:
        """Turns with unrecognised roles must not appear in the message list."""
        from langchain_core.messages import HumanMessage, SystemMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        history: list[HistoryTurn] = [
            {"role": cast(Literal["user", "assistant"], "system"), "content": "injected system turn"}
        ]
        await classifier.classify("the query", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        # Only SystemMessage + HumanMessage(query) — the unknown-role turn is dropped
        assert len(msgs) == 2
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "the query"

    @pytest.mark.asyncio
    async def test_history_capped_at_six_turns(self) -> None:
        """Only the last 6 history turns are forwarded to the chain."""
        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        history: list[HistoryTurn] = [{"role": "user", "content": f"turn {i}"} for i in range(8)]
        await classifier.classify("final query", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        # 1 SystemMessage + 6 history turns + 1 current query = 8
        assert len(msgs) == 8
        # First history turn in messages should be turn 2 (index 2), not turn 0
        assert msgs[1].content == "turn 2"

    @pytest.mark.asyncio
    async def test_query_appears_exactly_once_when_history_does_not_end_with_it(self) -> None:
        """classify() always appends the query — callers must not include it in history."""
        from langchain_core.messages import HumanMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        history: list[HistoryTurn] = [{"role": "assistant", "content": "What topic?"}]
        await classifier.classify("machine learning", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        human_contents = [m.content for m in msgs if isinstance(m, HumanMessage)]
        assert human_contents.count("machine learning") == 1

    @pytest.mark.asyncio
    async def test_attached_document_names_prepended_to_user_message(self) -> None:
        """attached_document_names are injected as a prefix in the HumanMessage sent to the chain."""
        from langchain_core.messages import HumanMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        await classifier.classify("summarise chapter 1", attached_document_names=["lecture.pdf", "notes.pdf"])
        (msgs,), _ = mock_chain.ainvoke.call_args
        last_msg = msgs[-1]
        assert isinstance(last_msg, HumanMessage)
        assert (
            '[The user has attached the following documents to this conversation: "lecture.pdf", "notes.pdf"]'
            in last_msg.content
        )
        assert "summarise chapter 1" in last_msg.content

    @pytest.mark.asyncio
    async def test_attached_document_names_none_leaves_query_unchanged(self) -> None:
        """When attached_document_names is None the HumanMessage is the bare query string."""
        from langchain_core.messages import HumanMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        await classifier.classify("design a quiz", attached_document_names=None)
        (msgs,), _ = mock_chain.ainvoke.call_args
        last_msg = msgs[-1]
        assert isinstance(last_msg, HumanMessage)
        assert last_msg.content == "design a quiz"

    @pytest.mark.asyncio
    async def test_query_duplicated_when_caller_includes_it_in_history(self) -> None:
        """Documents the double-send bug: if the caller passes the current query as the
        last history entry, it will appear twice in the message list. Callers are
        responsible for excluding the current message from history (use db_messages[:-1]).
        """
        from langchain_core.messages import HumanMessage

        classifier, mock_chain = _build_classifier()
        mock_chain.ainvoke = AsyncMock(return_value=_ScopeResult(in_scope=True))
        # Caller incorrectly includes the current query as the last history entry
        history: list[HistoryTurn] = [{"role": "user", "content": "machine learning"}]
        await classifier.classify("machine learning", history=history)
        (msgs,), _ = mock_chain.ainvoke.call_args
        human_contents = [m.content for m in msgs if isinstance(m, HumanMessage)]
        assert human_contents.count("machine learning") == 2
