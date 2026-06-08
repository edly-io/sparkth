"""Shared utilities for RAG retrieval — file lookup, chunk formatting, and batch validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.log import get_logger

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING only to avoid a runtime cycle: app.models.drive
    # imports RagStatus from app.lib.rag, which imports this module.
    # TODO: this circular dependency will be resolved once the Document API gets implemented
    from app.models.drive import DriveFile

from app.rag.enums import RagStatus
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError
from app.rag.types import SimilarityResult

logger = get_logger(__name__)


async def _lookup_drive_file(
    session: AsyncSession,
    user_id: int,
    file_db_id: int,
) -> DriveFile:
    from app.models.drive import DriveFile  # lazy — see TYPE_CHECKING note on the cycle

    result = await session.exec(
        select(DriveFile).where(
            col(DriveFile.id) == file_db_id,
            col(DriveFile.user_id) == user_id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
    )
    drive_file_raw: DriveFile | None = result.first()

    if drive_file_raw is None:
        logger.warning("DriveFile not found: id=%d user_id=%d", file_db_id, user_id)
        raise DriveFileNotFoundError(f"File with id={file_db_id} not found or not accessible.")

    drive_file = drive_file_raw

    if drive_file.rag_status != RagStatus.READY:
        status_str = str(drive_file.rag_status or "None")
        logger.warning("RAG not ready: file_db_id=%d status=%s", file_db_id, status_str)
        raise RAGNotReadyError(file_db_id, status_str)

    return drive_file


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


async def validate_files_ready(session: AsyncSession, user_id: int, file_ids: list[int]) -> None:
    """Verify every file is owned by user_id and in READY state.

    Raises:
        DriveFileNotFoundError: a file id is missing or not owned by the user.
        RAGNotReadyError: a file exists but its rag_status is not READY.
    """
    from app.models.drive import DriveFile  # lazy — see TYPE_CHECKING note on the cycle

    result = await session.exec(
        select(DriveFile).where(
            col(DriveFile.id).in_(file_ids),
            col(DriveFile.user_id) == user_id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
    )
    found = {f.id: f for f in result.all()}
    for file_id in file_ids:
        drive_file = found.get(file_id)
        if drive_file is None:
            logger.warning("DriveFile not found: id=%d user_id=%d", file_id, user_id)
            raise DriveFileNotFoundError(f"File with id={file_id} not found or not accessible.")
        if drive_file.rag_status != RagStatus.READY:
            status_str = str(drive_file.rag_status or "None")
            logger.warning("RAG not ready: file_db_id=%d status=%s", file_id, status_str)
            raise RAGNotReadyError(file_id, status_str)
