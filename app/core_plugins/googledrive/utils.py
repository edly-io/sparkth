"""RAG pipeline utilities for Google Drive file processing."""

import asyncio
import ctypes
import gc
import hashlib
import sys

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.googledrive.client import GoogleDriveClient
from app.core_plugins.googledrive.config import get_googledrive_settings
from app.core_plugins.googledrive.exceptions import GoogleDriveAPIError
from app.lib.db import session_scope
from app.lib.log import get_logger
from app.lib.rag import (
    RagStatus,
    ScannedPDFError,
    UnsupportedFileTypeError,
    ingest_document,
)
from app.models.drive import DriveFile, DriveFolder
from app.rag.models import DriveFileChunkLink  # duplicate-file path (residual; see #398)

logger = get_logger(__name__)


def _resolve_filename(drive_file: DriveFile) -> str:
    """Return the effective filename, converting Google-native types to .pdf."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in GoogleDriveClient.EXPORT_MIME_MAP:
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    return filename


async def _set_rag_status(
    session: AsyncSession,
    drive_file: DriveFile,
    status: RagStatus,
    error: str | None = None,
) -> None:
    """Update rag_status on a DriveFile and commit."""
    drive_file.rag_status = status
    drive_file.rag_error = error[:1000] if error and status == RagStatus.FAILED else None
    drive_file.update_timestamp()
    session.add(drive_file)
    await session.commit()


async def _download_file(access_token: str, drive_file: DriveFile) -> bytes:
    """Download a file's content from Google Drive."""
    async with GoogleDriveClient(access_token) as client:
        return await client.download_file(
            drive_file.drive_file_id,
            mime_type=drive_file.mime_type,
        )


async def _find_duplicate_file(
    session: AsyncSession, user_id: int, drive_file: DriveFile, content_hash: str
) -> DriveFile | None:
    """Find another DriveFile with the same content hash that is already processed."""
    result = await session.exec(
        select(DriveFile).where(
            col(DriveFile.user_id) == user_id,
            col(DriveFile.content_hash) == content_hash,
            col(DriveFile.rag_status) == RagStatus.READY,
            col(DriveFile.id) != drive_file.id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
    )
    return result.first()


async def _create_missing_links(session: AsyncSession, drive_file_id: int, chunk_ids: set[int]) -> None:
    """Insert bridge-table links for chunk_ids not already linked to drive_file_id."""
    already_linked = await session.scalars(
        select(DriveFileChunkLink.chunk_id).where(
            DriveFileChunkLink.drive_file_id == drive_file_id,
        )
    )
    existing_ids = set(already_linked.all())
    new_links = [DriveFileChunkLink(drive_file_id=drive_file_id, chunk_id=cid) for cid in chunk_ids - existing_ids]
    if new_links:
        session.add_all(new_links)
        await session.flush()


async def _link_chunks_from_duplicate(session: AsyncSession, drive_file_id: int, source_file_id: int) -> None:
    """Copy bridge-table links from an existing duplicate file, skipping any that already exist."""
    source_links = await session.scalars(
        select(DriveFileChunkLink.chunk_id).where(
            DriveFileChunkLink.drive_file_id == source_file_id,
        )
    )
    wanted_ids = set(source_links.all())
    await _create_missing_links(session, drive_file_id, wanted_ids)


async def _reject_if_oversized(
    session: AsyncSession,
    drive_file: DriveFile,
    size_bytes: int,
    filename: str,
    limit_mb: int,
) -> bool:
    """Mark the file FAILED and return True if size_bytes exceeds the limit; else return False."""
    if size_bytes <= limit_mb * 1024 * 1024:
        return False
    logger.warning(
        "Skipping '%s': size %d bytes exceeds INGESTION_MAX_FILE_SIZE_MB=%d.",
        filename,
        size_bytes,
        limit_mb,
    )
    await _set_rag_status(
        session,
        drive_file,
        RagStatus.FAILED,
        error=f"File too large for RAG ingestion (limit: {limit_mb} MB)",
    )
    return True


async def _ingest_drive_file(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    session: AsyncSession,
    filename: str,
    file_id: int,
) -> None:
    """Download, guard, dedup-check, and ingest one Drive file (the happy path).

    Sets PROCESSING/READY status and may early-return after a size guard or a
    duplicate match. Raises ingestion/Drive exceptions for the caller to map.
    """
    settings = get_googledrive_settings()
    limit_mb = settings.INGESTION_MAX_FILE_SIZE_MB

    await _set_rag_status(session, drive_file, RagStatus.PROCESSING)
    await session.refresh(drive_file)

    if drive_file.size is not None and await _reject_if_oversized(
        session, drive_file, drive_file.size, filename, limit_mb
    ):
        return

    file_bytes = await _download_file(access_token, drive_file)
    if await _reject_if_oversized(session, drive_file, len(file_bytes), filename, limit_mb):
        return

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    drive_file.content_hash = content_hash
    session.add(drive_file)
    await session.flush()

    duplicate = await _find_duplicate_file(session, user_id, drive_file, content_hash)
    if duplicate and duplicate.id is not None:
        await _link_chunks_from_duplicate(session, file_id, duplicate.id)
        await _set_rag_status(session, drive_file, RagStatus.READY)
        logger.info(
            "Duplicate document '%s' (hash=%s) — linked to existing chunks from '%s'.",
            filename,
            content_hash[:12],
            duplicate.name,
        )
        return

    result = await ingest_document(
        user_id=user_id,
        owner_file_id=file_id,
        file_bytes=file_bytes,
        filename=filename,
    )
    await _set_rag_status(session, drive_file, RagStatus.READY)
    logger.info(
        "RAG processing complete for '%s': %d new chunks stored, %d reused.",
        filename,
        result.new_chunks,
        result.reused_chunks,
    )


async def _process_single_file(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    session: AsyncSession,
) -> None:
    """Process one Drive file: run the ingestion pipeline and map failures to RagStatus.

    Owns Drive concerns only (status lifecycle + error translation). The actual
    download/ingest pipeline lives in _ingest_drive_file; chunking/storage is
    delegated to app.lib.rag.ingest_document.
    """
    filename = _resolve_filename(drive_file)
    log_name = drive_file.name or filename

    file_id = drive_file.id
    if file_id is None:
        logger.error("Cannot process file '%s' without a database ID.", log_name)
        return

    try:
        await _ingest_drive_file(drive_file, user_id, access_token, session, filename, file_id)
    except UnsupportedFileTypeError:
        logger.debug("Skipping unsupported file type for RAG: %s", filename)
        await _set_rag_status(session, drive_file, RagStatus.READY)
    except ScannedPDFError:
        logger.warning("RAG processing rejected scanned PDF '%s'", log_name)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error=ScannedPDFError.USER_MESSAGE)
    except GoogleDriveAPIError as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Google Drive error")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Could not reach Google Drive")
    except httpx.HTTPStatusError as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await _set_rag_status(
            session, drive_file, RagStatus.FAILED, error=f"Google Drive returned {e.response.status_code}"
        )
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Processing failed")
    except IntegrityError:
        logger.error("RAG processing failed for '%s': database integrity error", log_name)
        await session.rollback()
        await session.refresh(drive_file)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Database integrity error")
    except Exception as e:
        # Catch (then re-raise) all remaining exceptions so the file's rag_status
        # is never left stale; the re-raise surfaces the unexpected failure upstream.
        logger.error("Unknown error during RAG processing for '%s': %s / %s", log_name, e.__class__, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Unknown error")
        raise
    finally:
        session.expunge_all()
        gc.collect()


async def process_folder_rag(
    folder_id: int,
    user_id: int,
    access_token: str,
) -> None:
    """Run the RAG pipeline for all supported files in a synced folder."""
    async with session_scope() as session:
        folder_result = await session.exec(select(DriveFolder).where(DriveFolder.id == folder_id))
        folder = folder_result.first()
        if folder is None:
            logger.warning("process_folder_rag: folder %d not found.", folder_id)
            return

        result = await session.exec(
            select(DriveFile).where(
                col(DriveFile.folder_id) == folder_id,
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        files = result.all()

    if not files:
        return

    semaphore = asyncio.Semaphore(get_googledrive_settings().INGESTION_CONCURRENCY)

    async def _process_with_own_session(drive_file: DriveFile) -> None:
        async with semaphore:
            async with session_scope() as file_session:
                await _process_single_file(drive_file, user_id, access_token, file_session)
            # Session is now fully closed: connection returned to pool, identity map
            # cleared. Run GC + malloc_trim here so freed connection buffers and
            # ORM object memory are reclaimed before the next file starts.
            gc.collect()
            if sys.platform == "linux":
                try:
                    ctypes.CDLL("libc.so.6").malloc_trim(0)
                except (OSError, AttributeError):
                    pass

    pending_files = [df for df in files if df.rag_status not in (RagStatus.READY, RagStatus.PROCESSING)]
    # Capture file names before sessions close (avoid detached instance errors)
    pending_with_names = [(df, df.name) for df in pending_files]
    pending = [_process_with_own_session(df) for df, _ in pending_with_names]
    if pending:
        results = await asyncio.gather(*pending, return_exceptions=True)
        for i, task_result in enumerate(results):
            if isinstance(task_result, BaseException):
                _, file_name = pending_with_names[i]
                logger.error(
                    "RAG processing failed for '%s': %s",
                    file_name,
                    task_result,
                    exc_info=task_result,
                )
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            logger.warning(
                "RAG processing for folder '%s': %d/%d files had errors.",
                folder.drive_folder_name,
                len(errors),
                len(pending),
            )
