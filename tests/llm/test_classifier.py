"""Unit tests for LLM-based scope classifier."""

from typing import Literal, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

from app.llm.classifier import HistoryTurn, ScopeClassifier, _ScopeResult


def _build_classifier(provider: str = "anthropic") -> tuple["ScopeClassifier", AsyncMock]:
    """Construct a ScopeClassifier with a mocked LangChain client.

    Returns (classifier, mock_chain) where mock_chain.ainvoke controls responses.
    """
    chat_cls = {
        "anthropic": "app.llm.classifier.ChatAnthropic",
        "openai": "app.llm.classifier.ChatOpenAI",
        "google": "app.llm.classifier.ChatGoogleGenerativeAI",
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
        with patch("app.llm.classifier.ChatAnthropic") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="anthropic", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "claude-haiku-4-5"

    def test_openai_uses_mini_model(self) -> None:
        with patch("app.llm.classifier.ChatOpenAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="openai", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "gpt-4o-mini"

    def test_google_uses_flash_model(self) -> None:
        with patch("app.llm.classifier.ChatGoogleGenerativeAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="google", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("model") == "gemini-2.0-flash"

    def test_temperature_is_zero_for_determinism(self) -> None:
        with patch("app.llm.classifier.ChatAnthropic") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="anthropic", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("temperature") == 0

    def test_temperature_is_zero_for_openai(self) -> None:
        with patch("app.llm.classifier.ChatOpenAI") as MockChat:
            mock_llm = MagicMock()
            mock_llm.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_llm
            ScopeClassifier(provider_name="openai", api_key="test")
        _, kwargs = MockChat.call_args
        assert kwargs.get("temperature") == 0

    def test_temperature_is_zero_for_google(self) -> None:
        with patch("app.llm.classifier.ChatGoogleGenerativeAI") as MockChat:
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
