"""RAG pipeline utilities for Google Drive file processing."""

import hashlib
import logging
from pathlib import Path

from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_engine
from app.core_plugins.googledrive.client import GoogleDriveClient
from app.models.drive import DriveFile, DriveFolder
from app.rag.chunking import chunk_document
from app.rag.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.rag.extraction import extract_to_markdown
from app.rag.models import DocumentChunk, DriveFileChunkLink
from app.rag.store import ChunkInput, VectorStoreService
from app.rag.types import Chunk

logger = logging.getLogger(__name__)

_RAG_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({"pdf", "docx", "html", "htm", "txt", "md"})


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
    return ext in _RAG_SUPPORTED_EXTENSIONS


def _set_rag_status(session: Session, drive_file: DriveFile, status: str) -> None:
    """Update rag_status on a DriveFile and commit."""
    drive_file.rag_status = status
    drive_file.update_timestamp()
    session.add(drive_file)
    session.commit()


async def _download_file(access_token: str, drive_file: DriveFile) -> bytes:
    """Download a file's content from Google Drive."""
    async with GoogleDriveClient(access_token) as client:
        return await client.download_file(
            drive_file.drive_file_id,
            mime_type=drive_file.mime_type,
        )


def _find_duplicate_file(session: Session, user_id: int, drive_file: DriveFile, content_hash: str) -> DriveFile | None:
    """Find another DriveFile with the same content hash that is already processed."""
    return session.exec(
        select(DriveFile).where(
            DriveFile.user_id == user_id,
            DriveFile.content_hash == content_hash,
            DriveFile.rag_status == "ready",
            DriveFile.id != drive_file.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).first()


async def _link_chunks_from_duplicate(drive_file_id: int, source_file_id: int) -> None:
    """Copy bridge-table links from an existing duplicate file, skipping any that already exist."""
    async with AsyncSession(async_engine, expire_on_commit=False) as async_session:
        source_links = await async_session.execute(
            select(DriveFileChunkLink.chunk_id).where(
                DriveFileChunkLink.drive_file_id == source_file_id,
            )
        )
        wanted_ids = {row[0] for row in source_links.all()}

        already_linked = await async_session.execute(
            select(DriveFileChunkLink.chunk_id).where(
                DriveFileChunkLink.drive_file_id == drive_file_id,
            )
        )
        existing_ids = {row[0] for row in already_linked.all()}

        for chunk_id in wanted_ids - existing_ids:
            async_session.add(DriveFileChunkLink(drive_file_id=drive_file_id, chunk_id=chunk_id))
        await async_session.commit()


async def _embed_and_store_chunks(
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

    async with AsyncSession(async_engine, expire_on_commit=False) as async_session:
        # Batch-lookup which chunk hashes already exist
        existing_rows = await async_session.execute(
            select(DocumentChunk.id, DocumentChunk.chunk_content_hash).where(
                DocumentChunk.user_id == user_id,
                DocumentChunk.chunk_content_hash.in_(chunk_hashes),  # type: ignore[union-attr]
            )
        )
        existing_hash_to_id: dict[str, int] = {
            row.chunk_content_hash: row.id
            for row in existing_rows.all()  # type: ignore[union-attr]
        }

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
        new_rows = await store.store_chunks(async_session, user_id, new_chunk_inputs, provider)

        # Create bridge-table links, skipping any that already exist
        all_chunk_ids = {row.id for row in new_rows} | set(reused_chunk_ids)

        already_linked = await async_session.execute(
            select(DriveFileChunkLink.chunk_id).where(
                DriveFileChunkLink.drive_file_id == drive_file_id,
            )
        )
        existing_ids = {row[0] for row in already_linked.all()}

        for chunk_id in all_chunk_ids - existing_ids:
            async_session.add(DriveFileChunkLink(drive_file_id=drive_file_id, chunk_id=chunk_id))
        await async_session.commit()

    return len(new_chunk_inputs), len(reused_chunk_ids)


async def _process_single_file(
    drive_file: DriveFile,
    user_id: int,
    access_token: str,
    sync_session: Session,
    provider: BaseEmbeddingProvider,
    store: VectorStoreService,
) -> None:
    """Run the full RAG pipeline for a single Drive file."""
    filename = _resolve_filename(drive_file)

    if not _is_supported_for_rag(filename):
        logger.debug("Skipping unsupported file type for RAG: %s", filename)
        return

    try:
        _set_rag_status(sync_session, drive_file, "processing")

        file_bytes = await _download_file(access_token, drive_file)

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        drive_file.content_hash = content_hash

        # Duplicate document check
        duplicate = _find_duplicate_file(sync_session, user_id, drive_file, content_hash)
        if duplicate:
            await _link_chunks_from_duplicate(drive_file.id, duplicate.id)  # type: ignore[arg-type]
            _set_rag_status(sync_session, drive_file, "ready")
            logger.info(
                "Duplicate document '%s' (hash=%s) — linked to existing chunks from '%s'.",
                filename,
                content_hash[:12],
                duplicate.name,
            )
            return

        # Extract → Chunk
        extraction_result = extract_to_markdown(file_bytes, filename)
        chunks = chunk_document(extraction_result)

        if not chunks:
            _set_rag_status(sync_session, drive_file, "ready")
            return

        # Embed → Store → Link
        new_count, reused_count = await _embed_and_store_chunks(
            user_id,
            drive_file.id,
            chunks,
            provider,
            store,  # type: ignore[arg-type]
        )

        _set_rag_status(sync_session, drive_file, "ready")
        logger.info(
            "RAG processing complete for '%s': %d new chunks embedded, %d reused.",
            filename,
            new_count,
            reused_count,
        )

    except Exception:
        logger.exception("RAG processing failed for '%s'", drive_file.name)
        _set_rag_status(sync_session, drive_file, "failed")


async def process_folder_rag(
    folder: DriveFolder,
    user_id: int,
    access_token: str,
    sync_session: Session,
) -> None:
    """Run the RAG pipeline for all supported files in a synced folder."""
    files = sync_session.exec(
        select(DriveFile).where(
            DriveFile.folder_id == folder.id,
            DriveFile.is_deleted == False,  # noqa: E712
        )
    ).all()

    if not files:
        return

    provider = get_embedding_provider()
    store = VectorStoreService()

    for drive_file in files:
        if drive_file.rag_status == "ready":
            continue
        await _process_single_file(drive_file, user_id, access_token, sync_session, provider, store)
