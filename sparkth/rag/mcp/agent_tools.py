"""Build in-process LangChain tools for the RAG search agent.

Wraps the metadata functions in :mod:`sparkth.rag.mcp.tools` as LangChain
``StructuredTool`` instances, binding ``document_id`` via closure so the agent
only ever sees query-relevant arguments. This replaces the previous
out-of-process FastMCP server: the tools now run as direct Python calls.

The coroutines carry no audit wrapping of their own: every LangChain tool run
is recorded by the process-global callback handler
(:mod:`sparkth.lib.audit.callbacks`), and the agent runner in
:mod:`sparkth.rag.retrieval.agent` stamps the ``rag`` audit source.
"""

from langchain_core.tools import StructuredTool

from sparkth.rag.mcp import schemas, tools
from sparkth.rag.types import DocumentSection


def build_search_tools(document_id: int) -> list[StructuredTool]:
    """Build the RAG search agent's tools with document context pre-bound.

    Args:
        document_id: Document ID the search is scoped to, injected where relevant.

    Returns:
        LangChain tools exposing only the arguments the agent should choose.
    """

    async def get_document_metadata() -> schemas.DocumentMetadata | None:
        return await tools.get_document_metadata(document_id=document_id)

    async def list_document_sections() -> list[schemas.SectionKey]:
        return await tools.list_document_sections(document_id=document_id)

    async def get_chunk_stats() -> schemas.ChunkStats | None:
        return await tools.get_chunk_stats(document_id=document_id)

    async def get_document_structure() -> list[DocumentSection]:
        return await tools.get_document_structure(document_id=document_id)

    async def search_section_by_keyword(keyword: str) -> list[schemas.SectionKey]:
        return await tools.search_section_by_keyword(document_id=document_id, keyword=keyword)

    return [
        StructuredTool.from_function(
            coroutine=get_document_metadata,
            name="get_document_metadata",
            description="Get metadata for a specific document.",
        ),
        StructuredTool.from_function(
            coroutine=list_document_sections,
            name="list_document_sections",
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
