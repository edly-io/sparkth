"""Shared utilities for RAG retrieval — document lookup, chunk formatting, and batch validation."""

from __future__ import annotations

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document
from app.lib.log import get_logger
from app.rag.exceptions import DocumentNotFoundError, RAGNotReadyError
from app.rag.types import SimilarityResult

logger = get_logger(__name__)


async def _lookup_document(
    session: AsyncSession,
    user_id: int,
    document_id: int,
) -> Document:
    """Return the Document if owned by user_id, not deleted, and READY.

    Raises:
        DocumentNotFoundError: document missing, wrong owner, or soft-deleted.
        RAGNotReadyError: document exists but status is not READY.
    """
    result = await session.exec(
        select(Document).where(
            col(Document.id) == document_id,
            col(Document.user_id) == user_id,
            col(Document.is_deleted) == False,  # noqa: E712
        )
    )
    doc = result.first()

    if doc is None:
        logger.warning("Document not found: id=%d user_id=%d", document_id, user_id)
        raise DocumentNotFoundError(f"Document with id={document_id} not found or not accessible.")

    if doc.status != DocumentStatus.READY:
        status_str = str(doc.status)
        logger.warning("RAG not ready: document_id=%d status=%s", document_id, status_str)
        raise RAGNotReadyError(document_id, status_str)

    return doc


def format_chunks_as_context(source_name: str, results: list[SimilarityResult]) -> str:
    """Format retrieved chunks as a structured text block for the LLM."""
    if not results:
        return f"[DOCUMENT CONTEXT: {source_name}]\nNo relevant excerpts found."

    lines: list[str] = [
        f"[DOCUMENT CONTEXT: {source_name}]",
        "The following excerpts were retrieved from the document to inform your response:",
        "",
    ]
    for i, sr in enumerate(results, 1):
        chunk = sr.chunk
        header_parts = [p for p in [chunk.chapter, chunk.section, chunk.subsection] if p]
        section_label = " / ".join(header_parts) if header_parts else "General"
        lines.append(f"--- Excerpt {i} (Section: {section_label}) ---")
        lines.append(chunk.content.strip())
        lines.append("")

    return "\n".join(lines)


async def validate_files_ready(session: AsyncSession, user_id: int, document_ids: list[int]) -> None:
    """Verify every document is owned by user_id and in READY state.

    Raises:
        DocumentNotFoundError: a document id is missing or not owned by the user.
        RAGNotReadyError: a document exists but its status is not READY.
    """
    result = await session.exec(
        select(Document).where(
            col(Document.id).in_(document_ids),
            col(Document.user_id) == user_id,
            col(Document.is_deleted) == False,  # noqa: E712
        )
    )
    found = {d.id: d for d in result.all()}
    for doc_id in document_ids:
        doc = found.get(doc_id)
        if doc is None:
            logger.warning("Document not found: id=%d user_id=%d", doc_id, user_id)
            raise DocumentNotFoundError(f"Document with id={doc_id} not found or not accessible.")
        if doc.status != DocumentStatus.READY:
            status_str = str(doc.status)
            logger.warning("RAG not ready: document_id=%d status=%s", doc_id, status_str)
            raise RAGNotReadyError(doc_id, status_str)
