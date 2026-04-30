"""Tests for RAG MCP server."""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


import pytest

from app.rag_mcp.server import mcp


class TestRagMcpServer:
    """Test RAG MCP server."""

    @pytest.mark.asyncio
    async def test_server_has_expected_tools(self) -> None:
        """Test that the server has all five expected tools."""
        tools = await mcp.get_tools()

        # Tools is a dict keyed by tool name
        tool_names = list(tools.keys())

        expected_tools = [
            "_list_user_files",
            "_get_file_metadata",
            "_list_file_sections",
            "_get_chunk_stats",
            "_search_section_by_keyword",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not found in server"

    @pytest.mark.asyncio
    async def test_all_tools_have_non_empty_descriptions(self) -> None:
        """Test that all tools have descriptions."""
        tools = await mcp.get_tools()

        # Tools is a dict keyed by tool name
        for tool_name, tool_def in tools.items():
            assert hasattr(tool_def, "description"), f"Tool {tool_name} has no description attribute"
            assert tool_def.description is not None, f"Tool {tool_name} description is None"
            assert isinstance(tool_def.description, str), f"Tool {tool_name} description is not a string"
            assert len(tool_def.description) > 0, f"Tool {tool_name} has empty description"
