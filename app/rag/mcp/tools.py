"""Metadata-only tools for the RAG search agent."""

from __future__ import annotations

from typing import cast

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.db import session_scope
from app.lib.documents import Document, DocumentStatus
from app.lib.log import get_logger
from app.rag.mcp.schemas import ChunkStats, DocumentInfo, DocumentMetadata, DocumentSection, SectionKey
from app.rag.models import DocumentChunk, DocumentChunkLink

logger = get_logger(__name__)


async def _fetch_document(session: AsyncSession, document_id: int, user_id: int) -> Document | None:
    """Return the Document if it exists and is owned by user_id, else None."""
    result = await session.exec(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )
    return result.first()


async def list_user_documents(user_id: int) -> list[DocumentInfo]:
    """List all RAG-ready documents owned by a user."""

    async with session_scope() as session:
        result = await session.exec(
            select(Document).where(
                col(Document.user_id) == user_id,
                col(Document.is_deleted) == False,  # noqa: E712
                col(Document.status) == DocumentStatus.READY,
            )
        )
        documents = result.all()

        return [
            DocumentInfo(
                id=cast(int, doc.id),
                name=doc.name,
                mime_type=doc.mime_type,
                rag_status=doc.status,
            )
            for doc in documents
        ]


async def get_document_metadata(user_id: int, document_id: int) -> DocumentMetadata | None:
    """Get metadata for a specific document owned by a user."""

    async with session_scope() as session:
        doc = await _fetch_document(session, document_id, user_id)
        if doc is None:
            return None

        return DocumentMetadata(
            id=cast(int, doc.id),
            name=doc.name,
            mime_type=doc.mime_type,
            rag_status=doc.status,
        )


async def list_document_sections(user_id: int, document_id: int) -> list[SectionKey]:
    """List all distinct sections in a document."""

    async with session_scope() as session:
        doc = await _fetch_document(session, document_id, user_id)
        if doc is None:
            return []

        sections_result = await session.exec(
            select(
                DocumentChunk.chapter,
                DocumentChunk.section,
                DocumentChunk.subsection,
            )
            .join(DocumentChunkLink, col(DocumentChunk.id) == col(DocumentChunkLink.chunk_id))
            .where(
                DocumentChunk.user_id == user_id,
                col(DocumentChunkLink.document_id) == document_id,
            )
            .distinct()
        )
        return [SectionKey(chapter=row[0], section=row[1], subsection=row[2]) for row in sections_result.all()]


async def get_chunk_stats(user_id: int, document_id: int) -> ChunkStats | None:
    """Get statistics about chunks in a document (count and average token count)."""

    async with session_scope() as session:
        doc = await _fetch_document(session, document_id, user_id)
        if doc is None:
            return None

        stats_result = await session.exec(
            select(
                func.count().label("chunk_count"),
                func.avg(DocumentChunk.token_count).label("avg_token_count"),
            )
            .join(DocumentChunkLink, col(DocumentChunk.id) == col(DocumentChunkLink.chunk_id))
            .where(
                DocumentChunk.user_id == user_id,
                col(DocumentChunkLink.document_id) == document_id,
            )
        )
        row = stats_result.first()

        return ChunkStats(
            source_name=doc.name,
            chunk_count=row[0] if row else 0,
            avg_token_count=float(row[1]) if row and row[1] else None,
        )


async def get_document_structure(user_id: int, document_id: int) -> list[DocumentSection]:
    """Get the full ordered structure of a document with chunk positions.

    Returns sections in document order (ordered by minimum chunk id), with
    chunk counts and a zero-based position_index so the agent can reason about
    positional references like 'second half', 'last chapter', etc.
    """

    async with session_scope() as session:
        doc = await _fetch_document(session, document_id, user_id)
        if doc is None:
            return []

        structure_result = await session.exec(
            select(
                col(DocumentChunk.chapter),
                col(DocumentChunk.section),
                col(DocumentChunk.subsection),
                func.count().label("chunk_count"),
            )
            .join(DocumentChunkLink, col(DocumentChunk.id) == col(DocumentChunkLink.chunk_id))
            .where(
                DocumentChunk.user_id == user_id,
                col(DocumentChunkLink.document_id) == document_id,
            )
            .group_by(
                col(DocumentChunk.chapter),
                col(DocumentChunk.section),
                col(DocumentChunk.subsection),
            )
            .order_by(func.min(col(DocumentChunk.id)))
        )

        return [
            DocumentSection(
                source_name=doc.name,
                chapter=row[0],
                section=row[1],
                subsection=row[2],
                chunk_count=row[3],
                position_index=idx,
            )
            for idx, row in enumerate(structure_result.all())
        ]


async def search_section_by_keyword(user_id: int, document_id: int, keyword: str) -> list[SectionKey]:
    """Search for sections matching a keyword within a document."""
    if not keyword.strip():
        return []

    async with session_scope() as session:
        doc = await _fetch_document(session, document_id, user_id)
        if doc is None:
            return []

        keyword_safe = keyword.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        keyword_pattern = f"%{keyword_safe}%"

        search_result = await session.exec(
            select(
                DocumentChunk.chapter,
                DocumentChunk.section,
                DocumentChunk.subsection,
            )
            .join(DocumentChunkLink, col(DocumentChunk.id) == col(DocumentChunkLink.chunk_id))
            .where(
                DocumentChunk.user_id == user_id,
                col(DocumentChunkLink.document_id) == document_id,
                (
                    col(DocumentChunk.chapter).ilike(keyword_pattern, escape="\\")
                    | col(DocumentChunk.section).ilike(keyword_pattern, escape="\\")
                    | col(DocumentChunk.subsection).ilike(keyword_pattern, escape="\\")
                ),
            )
            .distinct()
        )

        return [SectionKey(chapter=row[0], section=row[1], subsection=row[2]) for row in search_result.all()]
