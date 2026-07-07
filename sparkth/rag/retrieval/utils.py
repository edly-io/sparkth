"""Shared utilities for RAG retrieval — document lookup, chunk formatting, and batch validation."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.log import get_logger
from sparkth.rag.exceptions import DocumentNotFoundError, RAGNotReadyError
from sparkth.rag.models import DocumentChunk

logger = get_logger(__name__)


async def _lookup_document(
    session: AsyncSession,
    document_id: int,
) -> Document:
    """Return the Document if it exists, is not deleted, and is READY.

    Raises:
        DocumentNotFoundError: document missing or soft-deleted.
        RAGNotReadyError: document exists but status is not READY.
    """
    result = await session.exec(
        select(Document).where(
            col(Document.id) == document_id,
            col(Document.is_deleted) == False,  # noqa: E712
        )
    )
    doc = result.first()

    if doc is None:
        logger.warning("Document not found: id=%d", document_id)
        raise DocumentNotFoundError(f"Document with id={document_id} not found.")

    if doc.status != DocumentStatus.READY:
        status_str = str(doc.status)
        logger.warning("RAG not ready: document_id=%d status=%s", document_id, status_str)
        raise RAGNotReadyError(document_id, status_str)

    return doc


def format_chunks_as_context(source_name: str, chunks: list[DocumentChunk]) -> str:
    """Format retrieved chunks as a structured text block for the LLM."""
    if not chunks:
        return f"[DOCUMENT CONTEXT: {source_name}]\nNo relevant excerpts found."

    lines: list[str] = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        header_parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        section_label = " / ".join(header_parts) if header_parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {section_label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")

    return "\n".join(lines)


async def validate_documents_ready(session: AsyncSession, document_ids: list[int]) -> None:
    """Verify every document exists, is not deleted, and is in READY state.

    Raises:
        DocumentNotFoundError: a document id is missing or soft-deleted.
        RAGNotReadyError: a document exists but its status is not READY.
    """
    result = await session.exec(
        select(Document).where(
            col(Document.id).in_(document_ids),
            col(Document.is_deleted) == False,  # noqa: E712
        )
    )
    found = {d.id: d for d in result.all()}
    for doc_id in document_ids:
        doc = found.get(doc_id)
        if doc is None:
            logger.warning("Document not found: id=%d", doc_id)
            raise DocumentNotFoundError(f"Document with id={doc_id} not found.")
        if doc.status != DocumentStatus.READY:
            status_str = str(doc.status)
            logger.warning("RAG not ready: document_id=%d status=%s", doc_id, status_str)
            raise RAGNotReadyError(doc_id, status_str)
