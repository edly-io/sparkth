from typing import Any

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.compose.hooks import COMPOSE_AGENTS, enabled_agents
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.frontend import get_plugin_display_info, get_plugin_sidebar_entry, plugin_has_frontend
from sparkth.lib.rag import SectionRef
from sparkth.plugins.rag.agent import (
    RAG,
    DocumentSections,
    SectionSelection,
    build_document_context,
)
from sparkth.plugins.rag.constants import NOTHING_MATCHED
from sparkth.plugins.rag.plugin import RagPlugin
from sparkth.rag.models import DocumentChunk, DocumentChunkLink

OWNER_ID = 1
OTHER_USER_ID = 2
STILL_PROCESSING = "Notes.pdf is still processing."


@pytest.fixture(autouse=True)
async def _owner_is_requesting() -> None:
    """Bound in the test's own context, so the binding ends with the test."""
    bind_current_user_id(OWNER_ID)


async def _seed(
    session: AsyncSession, *, user_id: int = OWNER_ID, status: DocumentStatus = DocumentStatus.READY
) -> None:
    """Document 10, Biology.pdf, with a chunk in each of two sections."""
    session.add(Document(id=10, user_id=user_id, name="Biology.pdf", status=status))
    chunks: list[dict[str, Any]] = [
        {"id": 1, "chapter": "Cells", "section": "Membranes", "content": "Membranes hold the cell together."},
        {"id": 2, "chapter": "Cells", "section": "Nucleus", "content": "The nucleus holds the DNA."},
    ]
    for chunk in chunks:
        session.add(DocumentChunk(source_name="Biology.pdf", subsection=None, **chunk))
        session.add(DocumentChunkLink(document_id=10, chunk_id=chunk["id"]))
    await session.commit()


def _selection(unavailable: str | None = None) -> SectionSelection:
    """The Nucleus section of document 10."""
    section = SectionRef(chapter="Cells", section="Nucleus")
    return SectionSelection(documents=[DocumentSections(document_id=10, sections=[section])], unavailable=unavailable)


def test_the_plugin_is_named_rag() -> None:
    assert RagPlugin().name == "rag"


def test_the_author_never_sees_the_plugin() -> None:
    plugin = RagPlugin()  # noqa: F841 - keeps the weakly-keyed hook entries alive

    assert get_plugin_display_info("rag") is None
    assert get_plugin_sidebar_entry("rag") is None
    assert not plugin_has_frontend("rag")


def test_the_plugin_contributes_the_rag_agent_once() -> None:
    plugin = RagPlugin()

    assert [item for owner, item in COMPOSE_AGENTS.iter_items() if owner is plugin] == [RAG]
    assert enabled_agents(set(), None).count(RAG) == 1


def test_the_agent_reads_documents_with_its_own_tools() -> None:
    assert [tool.name for tool in RAG.tools] == [
        "get_document_metadata",
        "get_document_structure",
        "search_section_by_keyword",
    ]


async def test_the_context_is_the_text_of_the_selected_sections(session: AsyncSession) -> None:
    await _seed(session)

    context = await build_document_context(_selection())

    assert "The nucleus holds the DNA." in context
    assert "Membranes" not in context


async def test_why_a_document_couldnt_be_read_follows_the_sections(session: AsyncSession) -> None:
    await _seed(session)

    context = await build_document_context(_selection(unavailable=STILL_PROCESSING))

    assert context.endswith(f"\n\n{STILL_PROCESSING}")
    assert "The nucleus holds the DNA." in context


@pytest.mark.parametrize(
    "seeded",
    [
        {"user_id": OTHER_USER_ID},
        {"status": DocumentStatus.PROCESSING},
    ],
    ids=["another_users_document", "a_document_still_processing"],
)
async def test_the_context_of_a_document_that_cant_be_read_is_nothing_matched(
    seeded: dict[str, Any], session: AsyncSession
) -> None:
    await _seed(session, **seeded)

    assert await build_document_context(_selection()) == NOTHING_MATCHED


async def test_the_context_of_an_empty_selection_is_nothing_matched() -> None:
    assert (
        await build_document_context(SectionSelection(unavailable=STILL_PROCESSING))
        == f"{NOTHING_MATCHED}\n\n{STILL_PROCESSING}"
    )
