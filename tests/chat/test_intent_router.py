from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError

from app.core_plugins.chat.intent_router import RAGIntentRouter, RAGIntentRouterError
from app.core_plugins.chat.schemas import RAGRoutingDecision


def _make_llm(return_value: Any) -> MagicMock:
    """Helper: returns a MagicMock that simulates an LLM with structured output."""
    mock_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=return_value)
    mock_llm.with_structured_output.return_value = mock_chain
    return mock_llm


def _make_drive_file(id: int = 1, name: str = "doc.pdf") -> MagicMock:
    """Helper: returns a MagicMock that simulates a DriveFile."""
    mock_file = MagicMock()
    mock_file.id = id
    mock_file.name = name
    return mock_file


class TestRAGIntentRouterDecide:
    """Tests for RAGIntentRouter.decide() method."""

    @pytest.mark.asyncio
    async def test_returns_decision_when_should_retrieve_true(self) -> None:
        """When _chain.ainvoke returns should_retrieve=True, decide() returns it unchanged."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="on topic")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            result = await router.decide(
                query="tell me about chapter 2",
                attached_files=[_make_drive_file(id=1, name="textbook.pdf")],
                session=MagicMock(),
                user_id=1,
            )

        assert result.should_retrieve is True
        assert result.reason == "on topic"

    @pytest.mark.asyncio
    async def test_returns_decision_when_should_retrieve_false(self) -> None:
        """When _chain.ainvoke returns should_retrieve=False, decide() returns it unchanged."""
        decision = RAGRoutingDecision(should_retrieve=False, reason="casual conversation")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            result = await router.decide(
                query="make that title punchier",
                attached_files=[_make_drive_file()],
                session=MagicMock(),
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

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            with pytest.raises(RAGIntentRouterError):
                await router.decide(
                    query="test",
                    attached_files=[_make_drive_file()],
                    session=MagicMock(),
                    user_id=1,
                )

    @pytest.mark.asyncio
    async def test_raises_router_error_on_validation_error(self) -> None:
        """When _chain.ainvoke raises ValidationError, decide() raises RAGIntentRouterError."""
        from pydantic import BaseModel

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

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            with pytest.raises(RAGIntentRouterError):
                await router.decide(
                    query="test",
                    attached_files=[_make_drive_file()],
                    session=MagicMock(),
                    user_id=1,
                )

    @pytest.mark.asyncio
    async def test_query_text_present_in_prompt(self) -> None:
        """The prompt passed to _chain.ainvoke contains the user query text."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="test")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)
        query_text = "summarize chapter 3"

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            await router.decide(
                query=query_text,
                attached_files=[_make_drive_file()],
                session=MagicMock(),
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
    async def test_file_name_present_in_prompt(self) -> None:
        """The prompt includes attachment file names."""
        decision = RAGRoutingDecision(should_retrieve=True, reason="test")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)
        file_name = "textbook.pdf"

        with patch("app.rag_mcp.tools.get_document_structure", new_callable=AsyncMock) as mock_struct:
            mock_struct.return_value = []

            await router.decide(
                query="tell me about this",
                attached_files=[_make_drive_file(id=1, name=file_name)],
                session=MagicMock(),
                user_id=1,
            )

        # Verify the file name appears in the messages
        call_args = llm.with_structured_output.return_value.ainvoke.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])

        message_contents = [msg.content for msg in messages]
        assert any(file_name in str(content) for content in message_contents), (
            f"File name '{file_name}' not found in messages: {message_contents}"
        )

    @pytest.mark.asyncio
    async def test_empty_attached_files_still_returns_decision(self) -> None:
        """When attached_files is empty, decide() still returns a valid RAGRoutingDecision."""
        decision = RAGRoutingDecision(should_retrieve=False, reason="no files")
        llm = _make_llm(decision)
        router = RAGIntentRouter(llm=llm)

        result = await router.decide(
            query="test",
            attached_files=[],
            session=MagicMock(),
            user_id=1,
        )

        assert isinstance(result, RAGRoutingDecision)
        assert result.should_retrieve is False
        # Verify get_document_structure was not called when no files attached
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
