"""Tests for the in-process RAG search tool builder."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.rag.mcp.agent_tools import build_search_tools


def _by_name(tools: list[Any]) -> dict[str, Any]:
    return {tool.name: tool for tool in tools}


class TestBuildSearchTools:
    """Unit tests for build_search_tools."""

    def test_builds_all_six_tools_with_expected_names(self) -> None:
        tools = build_search_tools(user_id=1, document_id=2)
        assert set(_by_name(tools)) == {
            "list_user_files",
            "get_file_metadata",
            "list_file_sections",
            "get_chunk_stats",
            "get_document_structure",
            "search_section_by_keyword",
        }

    def test_all_tools_have_non_empty_descriptions(self) -> None:
        for tool in build_search_tools(user_id=1, document_id=2):
            assert isinstance(tool.description, str)
            assert tool.description.strip()

    def test_context_only_tools_expose_no_llm_args(self) -> None:
        tools = _by_name(build_search_tools(user_id=1, document_id=2))
        for name in (
            "list_user_files",
            "get_file_metadata",
            "list_file_sections",
            "get_chunk_stats",
            "get_document_structure",
        ):
            assert set(tools[name].args_schema.model_fields) == set(), name

    def test_search_tool_exposes_only_keyword(self) -> None:
        tool = _by_name(build_search_tools(user_id=1, document_id=2))["search_section_by_keyword"]
        assert set(tool.args_schema.model_fields) == {"keyword"}

    @pytest.mark.asyncio
    async def test_invocation_injects_user_id_and_document_id(self) -> None:
        tool = _by_name(build_search_tools(user_id=42, document_id=10))["get_document_structure"]
        with patch("app.rag.mcp.agent_tools.tools.get_document_structure", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = []
            await tool.ainvoke({})
        mock_fn.assert_awaited_once_with(user_id=42, document_id=10)

    @pytest.mark.asyncio
    async def test_search_tool_injects_context_and_passes_keyword(self) -> None:
        tool = _by_name(build_search_tools(user_id=5, document_id=7))["search_section_by_keyword"]
        with patch("app.rag.mcp.agent_tools.tools.search_section_by_keyword", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = []
            await tool.ainvoke({"keyword": "intro"})
        mock_fn.assert_awaited_once_with(user_id=5, document_id=7, keyword="intro")

    @pytest.mark.asyncio
    async def test_list_user_files_injects_only_user_id(self) -> None:
        tool = _by_name(build_search_tools(user_id=9, document_id=99))["list_user_files"]
        with patch("app.rag.mcp.agent_tools.tools.list_user_files", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = []
            await tool.ainvoke({})
        mock_fn.assert_awaited_once_with(user_id=9)
