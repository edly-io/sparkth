"""The RAG agent: selects the sections of the author's attached documents that a request needs."""

from sparkth.lib.assets import read_asset
from sparkth.lib.compose.hooks import Agent, AgentStructuredReply
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.mcp.hooks import Tool
from sparkth.lib.rag import (
    SectionSelection,
    format_document_chunks_as_llm_context,
    get_document_metadata,
    get_document_structure,
    get_section_chunks,
    search_section_by_keyword,
)
from sparkth.plugins.rag.constants import NOTHING_MATCHED


async def build_document_context(section_selection: SectionSelection) -> str:
    """Render selected document sections as LLM context, followed by any retrieval failures."""
    chunks = [
        chunk
        for document in section_selection.documents
        for chunk in await get_section_chunks(
            document.document_id, [section.model_dump() for section in document.sections]
        )
    ]
    context_blocks = [format_document_chunks_as_llm_context(chunks) if chunks else NOTHING_MATCHED]
    if section_selection.unavailable:
        context_blocks.append(section_selection.unavailable)
    return "\n\n".join(context_blocks)


RAG = Agent(
    "rag",
    title="Attached documents",
    description=(
        "Finds the parts of the author's attached documents that a request needs, for the next step to use. "
        "Give it a step before any step that draws on what the attached documents say, such as a question "
        "about them, a summary, or a course, lesson or assessment built from them. Never use it when no "
        "documents are attached, or for chit-chat, confirmations, phrasing tweaks or anything unrelated to "
        "the documents."
    ),
    prompt=read_asset(__file__, "rag_prompt.txt"),
    status=gettext_noop("Searching your documents…"),
    tools=(Tool(get_document_metadata), Tool(get_document_structure), Tool(search_section_by_keyword)),
    structured_reply=AgentStructuredReply(SectionSelection, build_document_context),
)
