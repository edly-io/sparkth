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
from app.core_plugins.googledrive.models import DriveFile, DriveFolder
from app.lib.db import session_scope
from app.lib.documents import Document, DocumentStatus, create_document, update_document_status
from app.lib.log import get_logger
from app.lib.rag import (
    ScannedPDFError,
    UnsupportedFileTypeError,
    copy_document_chunk_links,
    ingest_document,
)

logger = get_logger(__name__)


def _resolve_filename(drive_file: DriveFile) -> str:
    """Return the effective filename, converting Google-native types to .pdf."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in GoogleDriveClient.EXPORT_MIME_MAP:
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    return filename


async def _download_file(access_token: str, drive_file: DriveFile) -> bytes:
    """Download a file's content from Google Drive."""
    async with GoogleDriveClient(access_token) as client:
        return await client.download_file(
            drive_file.drive_file_id,
            mime_type=drive_file.mime_type,
        )


async def _find_ready_duplicate_document_id(
    session: AsyncSession,
    user_id: int,
    drive_file: DriveFile,
    content_hash: str,
) -> int | None:
    """Return the document_id of an existing READY duplicate file, or None.

    Finds another DriveFile (same user, same content hash, not deleted, different id)
    whose Document is READY, indicating the content is already ingested.
    """
    result = await session.exec(
        select(Document.id)
        .join(DriveFile, col(DriveFile.document_id) == col(Document.id))
        .where(
            col(DriveFile.user_id) == user_id,
            col(DriveFile.content_hash) == content_hash,
            col(DriveFile.id) != drive_file.id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
            col(Document.status) == DocumentStatus.READY,
        )
    )
    return result.first()


async def _reject_if_oversized(
    session: AsyncSession,
    document_id: int,
    size_bytes: int,
    filename: str,
    limit_mb: int,
) -> bool:
    """Mark the document FAILED and return True if size_bytes exceeds the limit; else return False."""
    if size_bytes <= limit_mb * 1024 * 1024:
        return False
    logger.warning(
        "Skipping '%s': size %d bytes exceeds INGESTION_MAX_FILE_SIZE_MB=%d.",
        filename,
        size_bytes,
        limit_mb,
    )
    await update_document_status(
        session,
        document_id,
        DocumentStatus.FAILED,
        f"File too large for RAG ingestion (limit: {limit_mb} MB)",
    )
    await session.commit()
    return True


async def _ingest_drive_file(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    session: AsyncSession,
    filename: str,
    document_id: int,
) -> None:
    """Download, guard, dedup-check, and ingest one Drive file (the happy path).

    Sets PROCESSING/READY status on the Document and may early-return after a
    size guard or a duplicate match.
    """
    settings = get_googledrive_settings()
    limit_mb = settings.INGESTION_MAX_FILE_SIZE_MB

    await update_document_status(session, document_id, DocumentStatus.PROCESSING)
    await session.commit()
    await session.refresh(drive_file)

    if drive_file.size is not None and await _reject_if_oversized(
        session, document_id, drive_file.size, filename, limit_mb
    ):
        return

    file_bytes = await _download_file(access_token, drive_file)
    if await _reject_if_oversized(session, document_id, len(file_bytes), filename, limit_mb):
        return

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    drive_file.content_hash = content_hash
    session.add(drive_file)
    await session.flush()

    duplicate_document_id = await _find_ready_duplicate_document_id(session, user_id, drive_file, content_hash)
    if duplicate_document_id is not None:
        await copy_document_chunk_links(session, duplicate_document_id, document_id)
        await update_document_status(session, document_id, DocumentStatus.READY)
        await session.commit()
        logger.info(
            "Duplicate document '%s' (hash=%s) — linked to existing chunks.",
            filename,
            content_hash[:12],
        )
        return

    result = await ingest_document(filename, file_bytes, document_id, user_id)
    await update_document_status(session, document_id, DocumentStatus.READY)
    await session.commit()
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
    """Process one Drive file: run the ingestion pipeline and map failures to DocumentStatus.

    Owns Drive concerns only (Document status lifecycle + error translation). The actual
    download/ingest pipeline lives in _ingest_drive_file; chunking/storage is
    delegated to app.lib.rag.ingest_document.
    """
    filename = _resolve_filename(drive_file)
    log_name = drive_file.name or filename

    file_id = drive_file.id
    if file_id is None:
        logger.error("Cannot process file '%s' without a database ID.", log_name)
        return

    if drive_file.document_id is None:
        doc = await create_document(session, user_id, filename, drive_file.mime_type)
        drive_file.document_id = doc.id
        session.add(drive_file)
        await session.flush()

    assert drive_file.document_id is not None
    document_id: int = drive_file.document_id

    try:
        await _ingest_drive_file(drive_file, user_id, access_token, session, filename, document_id)
    except UnsupportedFileTypeError:
        logger.debug("Skipping unsupported file type for RAG: %s", filename)
        await update_document_status(session, document_id, DocumentStatus.READY)
        await session.commit()
    except ScannedPDFError:
        logger.warning("RAG processing rejected scanned PDF '%s'", log_name)
        await update_document_status(session, document_id, DocumentStatus.FAILED, ScannedPDFError.USER_MESSAGE)
        await session.commit()
    except GoogleDriveAPIError as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await update_document_status(session, document_id, DocumentStatus.FAILED, "Google Drive error")
        await session.commit()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await update_document_status(session, document_id, DocumentStatus.FAILED, "Could not reach Google Drive")
        await session.commit()
    except httpx.HTTPStatusError as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await update_document_status(
            session,
            document_id,
            DocumentStatus.FAILED,
            f"Google Drive returned {e.response.status_code}",
        )
        await session.commit()
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("RAG processing failed for '%s': %s", log_name, e)
        await update_document_status(session, document_id, DocumentStatus.FAILED, "Processing failed")
        await session.commit()
    except IntegrityError:
        logger.error("RAG processing failed for '%s': database integrity error", log_name)
        await session.rollback()
        await session.refresh(drive_file)
        await update_document_status(session, document_id, DocumentStatus.FAILED, "Database integrity error")
        await session.commit()
    finally:
        session.expunge_all()
        gc.collect()


async def _process_with_semaphore(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    semaphore: asyncio.Semaphore,
) -> None:
    """Process one file with semaphore-based concurrency control."""
    async with semaphore:
        async with session_scope() as file_session:
            await _process_single_file(drive_file, user_id, access_token, file_session)
        gc.collect()
        if sys.platform == "linux":
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except (OSError, AttributeError):
                pass


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

        files_result = await session.exec(
            select(DriveFile).where(
                col(DriveFile.folder_id) == folder_id,
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        files = files_result.all()

        if not files:
            return

        doc_ids = [f.document_id for f in files if f.document_id is not None]
        already_done_ids: set[int] = set()
        if doc_ids:
            done_result = await session.exec(
                select(Document.id).where(
                    col(Document.id).in_(doc_ids),
                    col(Document.status).in_([DocumentStatus.READY, DocumentStatus.PROCESSING]),
                )
            )
            already_done_ids = {did for did in done_result.all() if did is not None}

    pending_files = [f for f in files if f.document_id is None or f.document_id not in already_done_ids]

    if not pending_files:
        return

    semaphore = asyncio.Semaphore(get_googledrive_settings().INGESTION_CONCURRENCY)
    pending_with_names = [(df, df.name) for df in pending_files]
    tasks = [_process_with_semaphore(df, user_id, access_token, semaphore) for df, _ in pending_with_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
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
            len(pending_files),
        )
