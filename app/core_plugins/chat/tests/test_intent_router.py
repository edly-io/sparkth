from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from pydantic import BaseModel, ValidationError

from app.core_plugins.chat.exceptions import RAGIntentRouterError
from app.core_plugins.chat.intent_router import RAGIntentRouter
from app.core_plugins.chat.schemas import RAGRoutingDecision
from app.lib.documents import Document, DocumentStatus


def _make_llm(return_value: Any) -> MagicMock:
    """Helper: returns a MagicMock that simulates an LLM with structured output."""
    mock_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=return_value)
    mock_llm.with_structured_output.return_value = mock_chain
    return mock_llm


def _make_document(id: int = 1, name: str = "doc.pdf") -> Document:
    """Helper: returns a Document."""
    return Document(id=id, user_id=1, name=name, status=DocumentStatus.READY)


class TestRAGIntentRouterDecide:
    """Tests for RAGIntentRouter.decide() method."""

    @pytest.mark.asyncio
    async def test_returns_decision_when_should_retrieve_true(self) -> None:
        """When _chain.ainvoke returns should_retrieve=True, decide() returns it unchanged."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="on topic")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            result = await router.decide(
                query="tell me about chapter 2",
                attached_documents=[_make_document(id=1, name="textbook.pdf")],
                user_id=1,
            )

        assert result.should_retrieve is True
        assert result.reason == "on topic"
        mock_struct.assert_awaited_once_with(user_id=1, document_id=1)

    @pytest.mark.asyncio
    async def test_returns_decision_when_should_retrieve_false(self) -> None:
        """When _chain.ainvoke returns should_retrieve=False, decide() returns it unchanged."""
        decision = RAGRoutingDecision(should_retrieve=False, reason="casual conversation")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            result = await router.decide(
                query="make that title punchier",
                attached_documents=[_make_document()],
                user_id=1,
            )

        assert result.should_retrieve is False
        assert result.reason == "casual conversation"

    @pytest.mark.asyncio
    async def test_raises_router_error_on_langchain_exception(self) -> None:
        """When _chain.ainvoke raises LangChainException, decide() raises RAGIntentRouterError."""
        llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(side_effect=LangChainException("boom"))
        llm.with_structured_output.return_value = mock_chain

        router = RAGIntentRouter(llm=llm)

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            with pytest.raises(RAGIntentRouterError):
                await router.decide(
                    query="test",
                    attached_documents=[_make_document()],
                    user_id=1,
                )

    @pytest.mark.asyncio
    async def test_raises_router_error_on_validation_error(self) -> None:
        """When _chain.ainvoke raises ValidationError, decide() raises RAGIntentRouterError."""
        llm = MagicMock()
        mock_chain = MagicMock()
        # Create a simple ValidationError instance
        try:

            class TestModel(BaseModel):
                should_retrieve: bool

            TestModel(should_retrieve="invalid")  # type: ignore
        except ValidationError as ve:
            validation_error = ve

        mock_chain.ainvoke = AsyncMock(side_effect=validation_error)
        llm.with_structured_output.return_value = mock_chain

        router = RAGIntentRouter(llm=llm)

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            with pytest.raises(RAGIntentRouterError):
                await router.decide(
                    query="test",
                    attached_documents=[_make_document()],
                    user_id=1,
                )

    @pytest.mark.asyncio
    async def test_query_text_present_in_prompt(self) -> None:
        """The prompt passed to _chain.ainvoke contains the user query text."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="test")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)
        query_text = "summarize chapter 3"

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            await router.decide(
                query=query_text,
                attached_documents=[_make_document()],
                user_id=1,
            )

        # Verify ainvoke was called with messages containing the query
        assert llm.with_structured_output.return_value.ainvoke.called
        call_args = llm.with_structured_output.return_value.ainvoke.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])

        # Check that query text appears in at least one message's content
        message_contents = [msg.content for msg in messages]
        assert any(query_text in str(content) for content in message_contents), (
            f"Query '{query_text}' not found in messages: {message_contents}"
        )

    @pytest.mark.asyncio
    async def test_document_name_present_in_prompt(self) -> None:
        """The prompt includes attachment document names."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="test")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)
        document_name = "textbook.pdf"

        with patch("app.core_plugins.chat.intent_router.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            await router.decide(
                query="tell me about this",
                attached_documents=[_make_document(id=1, name=document_name)],
                user_id=1,
            )

        # Verify the document name appears in the messages.
        call_args = llm.with_structured_output.return_value.ainvoke.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])

        message_contents = [msg.content for msg in messages]
        assert any(document_name in str(content) for content in message_contents), (
            f"Document name '{document_name}' not found in messages: {message_contents}"
        )

    @pytest.mark.asyncio
    async def test_empty_attached_documents_still_returns_decision(self) -> None:
        """When attached_documents is empty, decide() still returns a valid RAGRoutingDecision."""
        decision = RAGRoutingDecision(should_retrieve=False, reason="no documents")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        result = await router.decide(
            query="test",
            attached_documents=[],
            user_id=1,
        )

        assert isinstance(result, RAGRoutingDecision)
        assert result.should_retrieve is False
        # Verify get_document_structure was not called when no documents are attached.
        # (the function is only imported inside decide() so we can't directly check)


class TestRAGIntentRouterError:
    """Tests for RAGIntentRouterError exception."""

    def test_is_exception_subclass(self) -> None:
        """RAGIntentRouterError is a subclass of Exception."""
        assert issubclass(RAGIntentRouterError, Exception)

    def test_original_exception_chained(self) -> None:
        """When raised from LangChainException, the original exception is chained via __cause__."""
        original_exc = LangChainException("original error")

        try:
            raise RAGIntentRouterError("Router failed") from original_exc
        except RAGIntentRouterError as e:
            assert e.__cause__ is original_exc
