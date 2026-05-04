"""Tests for RAG agent."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ConnectError, HTTPStatusError, Request, Response
from langchain_core.exceptions import LangChainException
from pydantic import BaseModel, ValidationError

from app.rag.agent import _bind_user_context, run_agentic_rag_search
from app.rag.exceptions import RAGRetrievalError
from app.rag.types import RAGSearchAgentResponse, SectionRef


class _SchemaWithBoth(BaseModel):
    user_id: int
    file_id: int
    keyword: str


class _SchemaUserOnly(BaseModel):
    user_id: int


class _SchemaNoContext(BaseModel):
    keyword: str


def _schema_to_args(schema: type[BaseModel]) -> dict[str, Any]:
    """Build a tool.args-compatible dict from a Pydantic schema."""
    type_map: dict[type, str] = {int: "integer", str: "string", float: "number", bool: "boolean"}
    return {
        name: {"type": type_map.get(field.annotation, "string"), "description": name}  # type: ignore[arg-type]
        for name, field in schema.model_fields.items()
    }


class TestBindUserContext:
    """Unit tests for _bind_user_context tool-binding helper."""

    def _make_tool(self, name: str, schema: type[BaseModel]) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        tool.description = f"desc of {name}"
        tool.args_schema = schema
        tool.args = _schema_to_args(schema)
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

    def test_passes_through_tool_when_args_raises(self) -> None:
        tool = MagicMock()
        tool.name = "broken"
        tool.description = "broken tool"
        type(tool).args = property(lambda self: (_ for _ in ()).throw(AttributeError("no args")))
        bound = _bind_user_context([tool], user_id=1, file_id=2)
        assert bound[0] is tool

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


def _make_validation_error() -> ValidationError:
    try:
        RAGSearchAgentResponse.model_validate({"source_name": [], "selected_sections": "x"})
    except ValidationError as exc:
        return exc
    raise AssertionError("ValidationError not raised")


class TestRunAgenticRagSearch:
    """Tests for run_agentic_rag_search covering the structured_response extraction and error paths."""

    def _patch_agent(self, agent: Any) -> Any:
        return patch("app.rag.agent.create_agent", return_value=agent)

    def _patch_mcp_client(self, side_effect: Exception | None = None) -> Any:
        mock_cls = MagicMock()
        if side_effect is not None:
            mock_cls.return_value.get_tools = AsyncMock(side_effect=side_effect)
        else:
            mock_cls.return_value.get_tools = AsyncMock(return_value=[])
        return patch("app.rag.agent.MultiServerMCPClient", mock_cls)

    def _patch_settings(self) -> Any:
        mock_settings = MagicMock()
        mock_settings.RAG_MCP_URL = "http://test-mcp:7728/mcp"
        return patch("app.rag.agent.get_settings", return_value=mock_settings)

    def _make_agent(self, return_value: dict[str, Any]) -> MagicMock:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(return_value=return_value)
        return agent

    @pytest.mark.asyncio
    async def test_happy_path_returns_structured_response(self) -> None:
        expected = RAGSearchAgentResponse(
            source_name="doc.pdf",
            selected_sections=[SectionRef(section="Introduction")],
        )
        agent = self._make_agent({"structured_response": expected})

        with self._patch_settings(), self._patch_mcp_client(), self._patch_agent(agent):
            result = await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

        assert result.source_name == "doc.pdf"
        assert len(result.selected_sections) == 1
        assert result.selected_sections[0].section == "Introduction"

    @pytest.mark.asyncio
    async def test_missing_structured_response_returns_empty(self) -> None:
        agent = self._make_agent({"messages": []})

        with self._patch_settings(), self._patch_mcp_client(), self._patch_agent(agent):
            result = await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

        assert result.source_name == ""
        assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_validation_error_returns_empty_response(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=_make_validation_error())

        with self._patch_settings(), self._patch_mcp_client(), self._patch_agent(agent):
            result = await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

        assert result.source_name == ""
        assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_connect_error_raises_retrieval_error(self) -> None:
        exc = ConnectError("connection refused", request=Request("GET", "http://test-mcp"))
        with self._patch_settings(), self._patch_mcp_client(side_effect=exc):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

    @pytest.mark.asyncio
    async def test_http_status_error_raises_retrieval_error(self) -> None:
        exc = HTTPStatusError("503", request=Request("GET", "http://test-mcp"), response=Response(503))
        with self._patch_settings(), self._patch_mcp_client(side_effect=exc):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

    @pytest.mark.asyncio
    async def test_langchain_exception_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=LangChainException("agent failed"))

        with self._patch_settings(), self._patch_mcp_client(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")

    @pytest.mark.asyncio
    async def test_value_error_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=ValueError("bad response"))

        with self._patch_settings(), self._patch_mcp_client(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(llm=MagicMock(), user_id=1, file_id=2, user_query="intro")
