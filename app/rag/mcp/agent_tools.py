"""Build in-process LangChain tools for the RAG search agent.

Wraps the metadata functions in :mod:`app.rag.mcp.tools` as LangChain
``StructuredTool`` instances, binding ``user_id``/``document_id`` via closure so the
agent only ever sees query-relevant arguments. This replaces the previous
out-of-process FastMCP server: the tools now run as direct Python calls.
"""

from langchain_core.tools import StructuredTool

from app.rag.mcp import schemas, tools


def build_search_tools(user_id: int, document_id: int) -> list[StructuredTool]:
    """Build the RAG search agent's tools with user/document context pre-bound.

    Args:
        user_id: User ID for row-level scoping, injected into every tool call.
        document_id: Document ID the search is scoped to, injected where relevant.

    Returns:
        LangChain tools exposing only the arguments the agent should choose.
    """

    async def list_user_files() -> list[schemas.FileInfo]:
        return await tools.list_user_files(user_id=user_id)

    async def get_file_metadata() -> schemas.FileMetadata | None:
        return await tools.get_file_metadata(user_id=user_id, document_id=document_id)

    async def list_file_sections() -> list[schemas.SectionKey]:
        return await tools.list_file_sections(user_id=user_id, document_id=document_id)

    async def get_chunk_stats() -> schemas.ChunkStats | None:
        return await tools.get_chunk_stats(user_id=user_id, document_id=document_id)

    async def get_document_structure() -> list[schemas.DocumentSection]:
        return await tools.get_document_structure(user_id=user_id, document_id=document_id)

    async def search_section_by_keyword(keyword: str) -> list[schemas.SectionKey]:
        return await tools.search_section_by_keyword(user_id=user_id, document_id=document_id, keyword=keyword)

    return [
        StructuredTool.from_function(
            coroutine=list_user_files,
            name="list_user_files",
            description="List all RAG-ready files owned by a user.",
        ),
        StructuredTool.from_function(
            coroutine=get_file_metadata,
            name="get_file_metadata",
            description="Get metadata for a specific file owned by a user.",
        ),
        StructuredTool.from_function(
            coroutine=list_file_sections,
            name="list_file_sections",
            description="List all distinct sections in a document.",
        ),
        StructuredTool.from_function(
            coroutine=get_chunk_stats,
            name="get_chunk_stats",
            description="Get statistics about chunks in a document (count and average token count).",
        ),
        StructuredTool.from_function(
            coroutine=get_document_structure,
            name="get_document_structure",
            description=(
                "Get the full ordered structure of a document with chunk counts and position indices. "
                "Use this to reason about positional references like 'second half', 'last chapter', "
                "'first section', etc."
            ),
        ),
        StructuredTool.from_function(
            coroutine=search_section_by_keyword,
            name="search_section_by_keyword",
            description="Search for sections matching a keyword within a document.",
        ),
    ]
