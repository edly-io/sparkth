"""Unit tests for LLM-based scope classifier."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

# Not yet importable — will fail with ImportError until classifier.py is created
from app.llm.classifier import ScopeClassifier, _ScopeResult


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
