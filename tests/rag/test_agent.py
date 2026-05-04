"""Tests for RAG agent."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ConnectError
from langchain_core.exceptions import LangChainException
from pydantic import BaseModel

from app.rag.agent import (
    AgentSearchDecision,
    _bind_user_context,
    _extract_decision,
    _make_submit_answer_tool,
    run_agentic_rag_search,
)
from app.rag.exceptions import RAGRetrievalError


class _SchemaWithBoth(BaseModel):
    user_id: int
    file_id: int
    keyword: str


class _SchemaUserOnly(BaseModel):
    user_id: int


class _SchemaNoContext(BaseModel):
    keyword: str


def _msg_with_tool_call(name: str, args: dict[str, Any]) -> MagicMock:
    msg = MagicMock()
    msg.tool_calls = [{"name": name, "args": args}]
    return msg


def _msg_no_tool_calls() -> MagicMock:
    msg = MagicMock()
    msg.tool_calls = []
    return msg


class TestBindUserContext:
    """Unit tests for _bind_user_context tool-binding helper."""

    def _make_tool(self, name: str, schema: type[BaseModel]) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        tool.description = f"desc of {name}"
        tool.args_schema = schema
        return tool

    def test_removes_user_id_and_file_id_from_schema(self) -> None:
        tool = self._make_tool("search", _SchemaWithBoth)
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert len(bound) == 1
        remaining = set(bound[0].args_schema.model_fields.keys())
        assert "user_id" not in remaining
        assert "file_id" not in remaining
        assert "keyword" in remaining

    def test_removes_user_id_only_when_file_id_absent(self) -> None:
        tool = self._make_tool("list_files", _SchemaUserOnly)
        bound = _bind_user_context([tool], user_id=7, file_id=99)
        assert set(bound[0].args_schema.model_fields.keys()) == set()

    def test_passes_through_tool_without_context_fields(self) -> None:
        tool = self._make_tool("other", _SchemaNoContext)
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert bound[0] is tool

    def test_preserves_tool_name_and_description(self) -> None:
        tool = self._make_tool("get_document_structure", _SchemaWithBoth)
        bound = _bind_user_context([tool], user_id=3, file_id=5)
        assert bound[0].name == "get_document_structure"
        assert bound[0].description == "desc of get_document_structure"

    @pytest.mark.asyncio
    async def test_injects_user_id_and_file_id_on_invocation(self) -> None:
        tool = self._make_tool("search", _SchemaWithBoth)
        captured: list[dict[str, Any]] = []

        async def _fake_ainvoke(data: dict[str, Any]) -> dict[str, Any]:
            captured.append(data)
            return data

        tool.ainvoke = _fake_ainvoke
        bound = _bind_user_context([tool], user_id=42, file_id=10)
        await bound[0].ainvoke({"keyword": "intro"})
        assert len(captured) == 1
        assert captured[0]["user_id"] == 42
        assert captured[0]["file_id"] == 10
        assert captured[0]["keyword"] == "intro"

    @pytest.mark.asyncio
    async def test_injects_only_user_id_for_user_only_schema(self) -> None:
        tool = self._make_tool("list_files", _SchemaUserOnly)
        captured: list[dict[str, Any]] = []

        async def _fake_ainvoke(data: dict[str, Any]) -> dict[str, Any]:
            captured.append(data)
            return data

        tool.ainvoke = _fake_ainvoke
        bound = _bind_user_context([tool], user_id=5, file_id=99)
        await bound[0].ainvoke({})
        assert captured[0] == {"user_id": 5}


class TestMakeSubmitAnswerTool:
    """Unit tests for the submit_answer response tool."""

    def test_tool_name(self) -> None:
        assert _make_submit_answer_tool().name == "submit_answer"

    def test_schema_has_source_name_and_selected_sections(self) -> None:
        schema = _make_submit_answer_tool().args_schema
        assert schema is not None
        assert isinstance(schema, type) and issubclass(schema, BaseModel)
        fields = set(schema.model_fields.keys())
        assert "source_name" in fields
        assert "selected_sections" in fields

    def test_schema_does_not_expose_user_or_file_id(self) -> None:
        schema = _make_submit_answer_tool().args_schema
        assert schema is not None
        assert isinstance(schema, type) and issubclass(schema, BaseModel)
        fields = set(schema.model_fields.keys())
        assert "user_id" not in fields
        assert "file_id" not in fields

    @pytest.mark.asyncio
    async def test_tool_is_a_no_op(self) -> None:
        tool = _make_submit_answer_tool()
        result = await tool.ainvoke({"source_name": "doc.pdf", "selected_sections": []})
        assert result is not None


class TestExtractDecision:
    """Unit tests for _extract_decision."""

    def test_extracts_from_tool_call(self) -> None:
        sections = [{"chapter": None, "section": "Intro", "subsection": None}]
        msg = _msg_with_tool_call("submit_answer", {"source_name": "doc.pdf", "selected_sections": sections})
        decision = _extract_decision([msg])
        assert decision is not None
        assert decision.source_name == "doc.pdf"
        assert decision.selected_sections == sections

    def test_returns_none_when_no_submit_answer_call(self) -> None:
        msg = _msg_no_tool_calls()
        assert _extract_decision([msg]) is None

    def test_returns_none_for_empty_messages(self) -> None:
        assert _extract_decision([]) is None

    def test_ignores_other_tool_calls(self) -> None:
        msg = _msg_with_tool_call("get_document_structure", {"user_id": 1, "file_id": 2})
        assert _extract_decision([msg]) is None

    def test_prefers_last_submit_answer_call(self) -> None:
        first = _msg_with_tool_call("submit_answer", {"source_name": "first.pdf", "selected_sections": []})
        last = _msg_with_tool_call("submit_answer", {"source_name": "last.pdf", "selected_sections": []})
        decision = _extract_decision([first, last])
        assert decision is not None
        assert decision.source_name == "last.pdf"

    def test_empty_sections_list(self) -> None:
        msg = _msg_with_tool_call("submit_answer", {"source_name": "doc.pdf", "selected_sections": []})
        decision = _extract_decision([msg])
        assert decision is not None
        assert decision.selected_sections == []


class TestAgentDecision:
    """Integration tests for run_agentic_rag_search."""

    @pytest.mark.asyncio
    async def test_returns_source_name_and_sections(self) -> None:
        """Agent result is extracted from the submit_answer tool call."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                sections = [
                    {"chapter": None, "section": "Introduction", "subsection": None},
                    {"chapter": None, "section": "Methods", "subsection": None},
                ]
                mock_graph = AsyncMock()
                mock_graph.ainvoke.return_value = {
                    "messages": [
                        _msg_with_tool_call(
                            "submit_answer",
                            {"source_name": "doc.pdf", "selected_sections": sections},
                        )
                    ]
                }
                mock_create_agent.return_value = mock_graph

                result = await run_agentic_rag_search(
                    llm=MagicMock(), user_id=1, file_id=1, user_query="What are the methods?"
                )

                assert isinstance(result, AgentSearchDecision)
                assert result.source_name == "doc.pdf"
                assert len(result.selected_sections) == 2
                assert result.selected_sections[0]["section"] == "Introduction"
                assert result.selected_sections[1]["section"] == "Methods"

    @pytest.mark.asyncio
    async def test_empty_decision_when_agent_does_not_call_submit_answer(self) -> None:
        """Falls back to empty decision when submit_answer is never called."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                mock_graph.ainvoke.return_value = {"messages": [_msg_no_tool_calls()]}
                mock_create_agent.return_value = mock_graph

                result = await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=1, user_query="query")

                assert result.source_name == ""
                assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_validation_error_from_submit_answer_returns_empty_decision(self) -> None:
        """ValidationError during tool invocation is caught and returns empty decision."""
        from pydantic import ValidationError

        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                mock_graph.ainvoke.side_effect = ValidationError.from_exception_data(title="test", line_errors=[])
                mock_create_agent.return_value = mock_graph

                result = await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=1, user_query="query")

                assert result.source_name == ""
                assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_mcp_client_connection_error_raises(self) -> None:
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_tools = AsyncMock(side_effect=ConnectError("Connection failed"))
            mock_client_class.return_value = mock_client

            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=1, user_query="query")

    @pytest.mark.asyncio
    async def test_agent_invocation_error_raises(self) -> None:
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                mock_graph.ainvoke.side_effect = LangChainException("Agent error")
                mock_create_agent.return_value = mock_graph

                with pytest.raises(RAGRetrievalError):
                    await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=1, user_query="query")

    @pytest.mark.asyncio
    async def test_submit_answer_tool_included_in_agent_tools(self) -> None:
        """submit_answer is appended to the tools passed to create_agent."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                mock_graph.ainvoke.return_value = {
                    "messages": [
                        _msg_with_tool_call("submit_answer", {"source_name": "f.pdf", "selected_sections": []})
                    ]
                }
                mock_create_agent.return_value = mock_graph

                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=1, user_query="q")

                _, call_args = mock_create_agent.call_args
                tools_passed = mock_create_agent.call_args[0][1]
                tool_names = [t.name for t in tools_passed]
                assert "submit_answer" in tool_names

    @pytest.mark.asyncio
    async def test_user_context_bound_to_tools(self) -> None:
        """user_id and file_id are pre-bound onto MCP tools, not in the system prompt."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                with patch("app.rag.agent._bind_user_context") as mock_bind:
                    mock_client = AsyncMock()
                    mock_client.__aenter__.return_value = mock_client
                    raw_tools: list[Any] = []
                    mock_client.get_tools = AsyncMock(return_value=raw_tools)
                    mock_client_class.return_value = mock_client
                    mock_bind.return_value = raw_tools

                    mock_graph = AsyncMock()
                    mock_graph.ainvoke.return_value = {
                        "messages": [
                            _msg_with_tool_call("submit_answer", {"source_name": "f.pdf", "selected_sections": []})
                        ]
                    }
                    mock_create_agent.return_value = mock_graph

                    await run_agentic_rag_search(llm=MagicMock(), user_id=5, file_id=10, user_query="What?")

                    mock_bind.assert_called_once_with(raw_tools, 5, 10)
