"""Tests for the in-process RAG search tool builder."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from sparkth.rag.mcp.agent_tools import build_search_tools


def _by_name(tools: list[Any]) -> dict[str, Any]:
    return {tool.name: tool for tool in tools}


class TestBuildSearchTools:
    """Unit tests for build_search_tools."""

    def test_builds_document_scoped_tools_with_expected_names(self) -> None:
        tools = build_search_tools(document_id=2)
        assert set(_by_name(tools)) == {
            "get_document_metadata",
            "list_document_sections",
            "get_chunk_stats",
            "get_document_structure",
            "search_section_by_keyword",
        }

    def test_all_tools_have_non_empty_descriptions(self) -> None:
        for tool in build_search_tools(document_id=2):
            assert isinstance(tool.description, str)
            assert tool.description.strip()

    def test_context_only_tools_expose_no_llm_args(self) -> None:
        tools = _by_name(build_search_tools(document_id=2))
        for name in (
            "get_document_metadata",
            "list_document_sections",
            "get_chunk_stats",
            "get_document_structure",
        ):
            assert set(tools[name].args_schema.model_fields) == set(), name

    def test_search_tool_exposes_only_keyword(self) -> None:
        tool = _by_name(build_search_tools(document_id=2))["search_section_by_keyword"]
        assert set(tool.args_schema.model_fields) == {"keyword"}

    @pytest.mark.asyncio
    async def test_invocation_injects_document_id(self) -> None:
        tool = _by_name(build_search_tools(document_id=10))["get_document_structure"]
        with patch("sparkth.rag.mcp.agent_tools.tools.get_document_structure", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = []
            await tool.ainvoke({})
        mock_fn.assert_awaited_once_with(document_id=10)

    @pytest.mark.asyncio
    async def test_search_tool_injects_document_id_and_passes_keyword(self) -> None:
        tool = _by_name(build_search_tools(document_id=7))["search_section_by_keyword"]
        with patch("sparkth.rag.mcp.agent_tools.tools.search_section_by_keyword", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = []
            await tool.ainvoke({"keyword": "intro"})
        mock_fn.assert_awaited_once_with(document_id=7, keyword="intro")
