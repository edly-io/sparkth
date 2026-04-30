"""RAG MCP server with metadata tools."""

from typing import Any

from fastmcp import FastMCP

from app.rag_mcp.tools import (
    get_chunk_stats,
    get_document_structure,
    get_file_metadata,
    list_file_sections,
    list_user_files,
    search_section_by_keyword,
)

mcp = FastMCP(
    name="SparkthRAGMetadata",
    instructions="Metadata-only tools for the Sparkth RAG pipeline. Returns document and section structure — no embeddings or raw content.",
)


@mcp.tool(description="List all RAG-ready files owned by a user.")
async def _list_user_files(user_id: int) -> list[dict[str, Any]]:
    return await list_user_files(user_id=user_id)


@mcp.tool(description="Get metadata for a specific file owned by a user.")
async def _get_file_metadata(user_id: int, file_id: int) -> dict[str, Any] | None:
    return await get_file_metadata(user_id=user_id, file_id=file_id)


@mcp.tool(description="List all distinct sections in a file.")
async def _list_file_sections(user_id: int, file_id: int) -> list[dict[str, Any]]:
    return await list_file_sections(user_id=user_id, file_id=file_id)


@mcp.tool(description="Get statistics about chunks in a file (count and average token count).")
async def _get_chunk_stats(user_id: int, file_id: int) -> dict[str, Any] | None:
    return await get_chunk_stats(user_id=user_id, file_id=file_id)


@mcp.tool(
    description="Get the full ordered structure of a document with chunk counts and position indices. "
    "Use this to reason about positional references like 'second half', 'last chapter', 'first section', etc."
)
async def _get_document_structure(user_id: int, file_id: int) -> list[dict[str, Any]]:
    return await get_document_structure(user_id=user_id, file_id=file_id)


@mcp.tool(description="Search for sections matching a keyword within a file.")
async def _search_section_by_keyword(user_id: int, file_id: int, keyword: str) -> list[dict[str, Any]]:
    return await search_section_by_keyword(user_id=user_id, file_id=file_id, keyword=keyword)
