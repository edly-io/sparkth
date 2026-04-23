"""RAG pipeline utilities for Google Drive file processing."""

import asyncio
import gc
import hashlib
import logging
from pathlib import Path

import httpx
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.db import async_engine
from app.core_plugins.googledrive.client import GoogleDriveAPIError, GoogleDriveClient
from app.models.drive import DriveFile, DriveFolder
from app.rag.chunking import chunk_document
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.extraction import SUPPORTED_EXTENSIONS, extract_to_markdown
from app.rag.memory_profiler import profile_memory
from app.rag.models import DocumentChunk, DriveFileChunkLink
from app.rag.provider import get_provider
from app.rag.store import ChunkInput, VectorStoreService
from app.rag.types import Chunk, RagStatus

logger = logging.getLogger(__name__)


def _resolve_filename(drive_file: DriveFile) -> str:
    """Return the effective filename, converting Google-native types to .pdf."""
    filename = drive_file.name
    mime_type = drive_file.mime_type or ""
    if mime_type in GoogleDriveClient.EXPORT_MIME_MAP:
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
    return filename


def _is_supported_for_rag(filename: str) -> bool:
    """Check whether the file extension is supported by the extraction module."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in SUPPORTED_EXTENSIONS


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
    result = await session.execute(
        select(DriveFile).where(
            col(DriveFile.user_id) == user_id,
            col(DriveFile.content_hash) == content_hash,
            col(DriveFile.rag_status) == RagStatus.READY,
            col(DriveFile.id) != drive_file.id,
            col(DriveFile.is_deleted) == False,  # noqa: E712
        )
    )
    return result.scalars().first()


async def _create_missing_links(session: AsyncSession, drive_file_id: int, chunk_ids: set[int]) -> None:
    """Insert bridge-table links for chunk_ids not already linked to drive_file_id."""
    already_linked = await session.execute(
        select(DriveFileChunkLink.chunk_id).where(
            DriveFileChunkLink.drive_file_id == drive_file_id,
        )
    )
    existing_ids = {row[0] for row in already_linked.all()}
    new_links = [DriveFileChunkLink(drive_file_id=drive_file_id, chunk_id=cid) for cid in chunk_ids - existing_ids]
    if new_links:
        session.add_all(new_links)
        await session.flush()


async def _link_chunks_from_duplicate(session: AsyncSession, drive_file_id: int, source_file_id: int) -> None:
    """Copy bridge-table links from an existing duplicate file, skipping any that already exist."""
    source_links = await session.execute(
        select(DriveFileChunkLink.chunk_id).where(
            DriveFileChunkLink.drive_file_id == source_file_id,
        )
    )
    wanted_ids = {row[0] for row in source_links.all()}
    await _create_missing_links(session, drive_file_id, wanted_ids)


async def _embed_and_store_chunks(
    session: AsyncSession,
    user_id: int,
    drive_file_id: int,
    chunks: list[Chunk],
    provider: BaseEmbeddingProvider,
    store: VectorStoreService,
) -> tuple[int, int]:
    """Embed new chunks, reuse existing ones, and create bridge-table links.

    Returns (new_count, reused_count).
    """
    chunk_hashes = [hashlib.sha256(c.content.encode()).hexdigest() for c in chunks]

    # Batch-lookup which chunk hashes already exist
    existing_rows = await session.execute(
        select(DocumentChunk.id, DocumentChunk.chunk_content_hash).where(
            DocumentChunk.user_id == user_id,
            DocumentChunk.chunk_content_hash.in_(chunk_hashes),  # type: ignore[union-attr]
        )
    )
    existing_hash_to_id: dict[str, int] = {row.chunk_content_hash: row.id for row in existing_rows.all()}

    # Split into new (need embedding) vs reused (just link)
    new_chunk_inputs: list[ChunkInput] = []
    reused_chunk_ids: list[int] = []

    for chunk, chunk_hash in zip(chunks, chunk_hashes):
        if chunk_hash in existing_hash_to_id:
            reused_chunk_ids.append(existing_hash_to_id[chunk_hash])
            logger.debug("Duplicate chunk (hash=%s) — reusing existing.", chunk_hash[:12])
        else:
            new_chunk_inputs.append(
                ChunkInput(
                    content=chunk.content,
                    source_name=chunk.metadata.source_name,
                    chapter=chunk.metadata.chapter,
                    section=chunk.metadata.section,
                    subsection=chunk.metadata.subsection,
                    chunk_content_hash=chunk_hash,
                )
            )

    # Embed and store only new chunks
    new_rows = await store.store_chunks(session, user_id, new_chunk_inputs, provider)

    # Create bridge-table links, skipping any that already exist
    all_chunk_ids: set[int] = {row.id for row in new_rows if row.id is not None} | set(reused_chunk_ids)
    await _create_missing_links(session, drive_file_id, all_chunk_ids)

    return len(new_chunk_inputs), len(reused_chunk_ids)


async def _process_single_file(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    session: AsyncSession,
    provider: BaseEmbeddingProvider,
    store: VectorStoreService,
) -> None:
    """Run the full RAG pipeline for a single Drive file."""
    filename = _resolve_filename(drive_file)

    if not _is_supported_for_rag(filename):
        logger.debug("Skipping unsupported file type for RAG: %s", filename)
        await _set_rag_status(session, drive_file, RagStatus.READY)
        return

    if drive_file.id is None:
        logger.error("Cannot process file '%s' without a database ID.", drive_file.name)
        return

    file_id: int = drive_file.id

    try:
        await _set_rag_status(session, drive_file, RagStatus.PROCESSING)

        async with profile_memory("pipeline_total", file=filename):
            async with profile_memory("download", file=filename):
                file_bytes = await _download_file(access_token, drive_file)

            # Reject files that exceed configured size limit
            max_bytes = get_settings().RAG_MAX_FILE_SIZE_MB * 1024 * 1024
            if len(file_bytes) > max_bytes:
                logger.warning(
                    "Skipping '%s': file size %d bytes exceeds RAG_MAX_FILE_SIZE_MB=%d.",
                    filename,
                    len(file_bytes),
                    get_settings().RAG_MAX_FILE_SIZE_MB,
                )
                await _set_rag_status(
                    session,
                    drive_file,
                    RagStatus.FAILED,
                    error=f"File too large for RAG ingestion (limit: {get_settings().RAG_MAX_FILE_SIZE_MB} MB)",
                )
                return


            content_hash = hashlib.sha256(file_bytes).hexdigest()
            drive_file.content_hash = content_hash
            session.add(drive_file)
            await session.flush()

            # Duplicate document check
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

            # Extract → Chunk (CPU-bound, run off the event loop)
            async with profile_memory("extraction", file=filename, size_bytes=len(file_bytes)):
                extraction_result = await asyncio.to_thread(extract_to_markdown, file_bytes, filename)

            # Release raw PDF bytes immediately — extractor has already copied
            # what it needs into extraction_result.markdown. Keeping file_bytes alive
            # through chunking wastes memory equal to the full file size.
            del file_bytes
            gc.collect()


            async with profile_memory("chunking", file=filename, markdown_chars=len(extraction_result.markdown)):
                chunks = await asyncio.to_thread(chunk_document, extraction_result)

            if not chunks:
                await _set_rag_status(session, drive_file, RagStatus.READY)
                return

            # Embed → Store → Link
            async with profile_memory("embed_and_store", file=filename, chunks=len(chunks)):
                new_count, reused_count = await _embed_and_store_chunks(
                    session,
                    user_id,
                    file_id,
                    chunks,
                    provider,
                    store,
                )

            await _set_rag_status(session, drive_file, RagStatus.READY)
            logger.info(
                "RAG processing complete for '%s': %d new chunks embedded, %d reused.",
                filename,
                new_count,
                reused_count,
            )

    except GoogleDriveAPIError as e:
        logger.error("RAG processing failed for '%s': %s", drive_file.name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Google Drive error")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error("RAG processing failed for '%s': %s", drive_file.name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Could not reach Google Drive")
    except httpx.HTTPStatusError as e:
        logger.error("RAG processing failed for '%s': %s", drive_file.name, e)
        await _set_rag_status(
            session, drive_file, RagStatus.FAILED, error=f"Google Drive returned {e.response.status_code}"
        )
    except (RuntimeError, ValueError, OSError) as e:
        logger.error("RAG processing failed for '%s': %s", drive_file.name, e)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Processing failed")
    except IntegrityError:
        logger.error("RAG processing failed for '%s': database integrity error", drive_file.name)
        await session.rollback()
        await session.refresh(drive_file)
        await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Database integrity error")
    except SQLAlchemyError as e:
        logger.error("Database error during RAG processing for '%s': %s", drive_file.name, e)
        try:
            await _set_rag_status(session, drive_file, RagStatus.FAILED, error="Database error")
        except SQLAlchemyError as status_err:
            logger.error(
                "Failed to set RAG status to FAILED for '%s': %s",
                drive_file.name,
                status_err,
            )


async def process_folder_rag(
    folder_id: int,
    user_id: int,
    access_token: str,
) -> None:
    """Run the RAG pipeline for all supported files in a synced folder."""
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        folder_result = await session.execute(select(DriveFolder).where(DriveFolder.id == folder_id))
        folder = folder_result.scalars().first()
        if folder is None:
            logger.warning("process_folder_rag: folder %d not found.", folder_id)
            return

        result = await session.execute(
            select(DriveFile).where(
                col(DriveFile.folder_id) == folder_id,
                col(DriveFile.is_deleted) == False,  # noqa: E712
            )
        )
        files = result.scalars().all()

    if not files:
        return

    provider = get_provider()
    store = VectorStoreService()
    semaphore = asyncio.Semaphore(get_settings().RAG_CONCURRENCY)

    async def _process_with_own_session(drive_file: DriveFile) -> None:
        async with semaphore:
            async with AsyncSession(async_engine, expire_on_commit=False) as file_session:
                await _process_single_file(drive_file, user_id, access_token, file_session, provider, store)

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
