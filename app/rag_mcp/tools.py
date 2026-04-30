"""Metadata-only tools for RAG MCP server."""

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, func, select

from app.core.logger import get_logger
from app.models.drive import DriveFile
from app.rag.models import DocumentChunk
from app.rag.types import RagStatus
from app.rag_mcp.db import get_async_session

logger = get_logger(__name__)


def _resolve_source_name(drive_file: DriveFile) -> str:
    source_name = drive_file.name
    if drive_file.mime_type and "google" in drive_file.mime_type.lower():
        if not source_name.lower().endswith(".pdf"):
            source_name += ".pdf"
    return source_name


async def list_user_files(user_id: int) -> list[dict[str, Any]]:
    """List all RAG-ready files owned by a user."""
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(DriveFile).where(
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                    DriveFile.rag_status == RagStatus.READY,
                )
            )
            files = result.scalars().all()
            return [
                {
                    "id": f.id,
                    "name": f.name,
                    "mime_type": f.mime_type,
                    "size": f.size,
                    "modified_time": f.modified_time.isoformat() if f.modified_time else None,
                    "rag_status": f.rag_status,
                }
                for f in files
            ]
    except SQLAlchemyError:
        logger.exception("Database error listing user files for user %s", user_id)
        raise


async def get_file_metadata(user_id: int, file_id: int) -> dict[str, Any] | None:
    """Get metadata for a specific file owned by a user."""
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(DriveFile).where(
                    DriveFile.id == file_id,
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                )
            )
            file = result.scalars().first()
            if not file:
                return None
            return {
                "id": file.id,
                "name": file.name,
                "rag_status": file.rag_status,
                "size": file.size,
                "modified_time": file.modified_time.isoformat() if file.modified_time else None,
            }
    except SQLAlchemyError:
        logger.exception("Database error getting file metadata for file %s, user %s", file_id, user_id)
        raise


async def list_file_sections(user_id: int, file_id: int) -> list[dict[str, Any]]:
    """List all distinct sections in a file."""
    try:
        async with get_async_session() as session:
            file_result = await session.execute(
                select(DriveFile).where(
                    DriveFile.id == file_id,
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                )
            )
            file = file_result.scalars().first()
            if not file:
                return []

            source_name = _resolve_source_name(file)

            sections_result = await session.execute(
                select(
                    DocumentChunk.chapter,
                    DocumentChunk.section,
                    DocumentChunk.subsection,
                )
                .where(
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.source_name == source_name,
                )
                .distinct()
            )
            return [{"chapter": row[0], "section": row[1], "subsection": row[2]} for row in sections_result.all()]
    except SQLAlchemyError:
        logger.exception("Database error listing sections for file %s, user %s", file_id, user_id)
        raise


async def get_chunk_stats(user_id: int, file_id: int) -> dict[str, Any] | None:
    """Get statistics about chunks in a file (count and average token count)."""
    try:
        async with get_async_session() as session:
            file_result = await session.execute(
                select(DriveFile).where(
                    DriveFile.id == file_id,
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                )
            )
            file = file_result.scalars().first()
            if not file:
                return None

            source_name = _resolve_source_name(file)

            stats_result = await session.execute(
                select(
                    func.count().label("chunk_count"),
                    func.avg(DocumentChunk.token_count).label("avg_token_count"),
                ).where(
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.source_name == source_name,
                )
            )
            row = stats_result.first()

            return {
                "source_name": source_name,
                "chunk_count": row[0] if row else 0,
                "avg_token_count": float(row[1]) if row and row[1] else None,
            }
    except SQLAlchemyError:
        logger.exception("Database error getting chunk stats for file %s, user %s", file_id, user_id)
        raise


async def get_document_structure(user_id: int, file_id: int) -> list[dict[str, Any]]:
    """Get the full ordered structure of a document with chunk positions.

    Returns sections in document order (ordered by minimum chunk id), with
    chunk counts and a zero-based position_index so the agent can reason about
    positional references like 'second half', 'last chapter', etc.
    """
    try:
        async with get_async_session() as session:
            file_result = await session.execute(
                select(DriveFile).where(
                    DriveFile.id == file_id,
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                )
            )
            file = file_result.scalars().first()
            if not file:
                return []

            source_name = _resolve_source_name(file)

            structure_result = await session.execute(
                select(
                    col(DocumentChunk.chapter),
                    col(DocumentChunk.section),
                    col(DocumentChunk.subsection),
                    func.count().label("chunk_count"),
                )
                .where(
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.source_name == source_name,
                )
                .group_by(
                    col(DocumentChunk.chapter),
                    col(DocumentChunk.section),
                    col(DocumentChunk.subsection),
                )
                .order_by(func.min(col(DocumentChunk.id)))
            )

            return [
                {
                    "chapter": row[0],
                    "section": row[1],
                    "subsection": row[2],
                    "chunk_count": row[3],
                    "position_index": idx,
                }
                for idx, row in enumerate(structure_result.all())
            ]
    except SQLAlchemyError:
        logger.exception("Database error getting document structure for file %s, user %s", file_id, user_id)
        raise


async def search_section_by_keyword(user_id: int, file_id: int, keyword: str) -> list[dict[str, Any]]:
    """Search for sections matching a keyword within a file."""
    if not keyword.strip():
        return []

    try:
        async with get_async_session() as session:
            file_result = await session.execute(
                select(DriveFile).where(
                    DriveFile.id == file_id,
                    DriveFile.user_id == user_id,
                    DriveFile.is_deleted == False,  # noqa: E712
                )
            )
            file = file_result.scalars().first()
            if not file:
                return []

            source_name = _resolve_source_name(file)
            keyword_pattern = f"%{keyword}%"

            search_result = await session.execute(
                select(
                    DocumentChunk.chapter,
                    DocumentChunk.section,
                    DocumentChunk.subsection,
                )
                .where(
                    DocumentChunk.user_id == user_id,
                    DocumentChunk.source_name == source_name,
                    (
                        col(DocumentChunk.chapter).ilike(keyword_pattern)
                        | col(DocumentChunk.section).ilike(keyword_pattern)
                        | col(DocumentChunk.subsection).ilike(keyword_pattern)
                    ),
                )
                .distinct()
            )

            return [{"chapter": row[0], "section": row[1], "subsection": row[2]} for row in search_result.all()]
    except SQLAlchemyError:
        logger.exception(
            "Database error searching sections for file %s, user %s, keyword %s", file_id, user_id, keyword
        )
        raise
