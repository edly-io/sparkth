"""Tests for app.rag.store.store_and_link_chunks — chunk storage + dedup + linking."""

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.models import DocumentChunk, DriveFileChunkLink
from app.rag.store import ChunkInput, ChunkStoreService, store_and_link_chunks
from app.rag.types import Chunk, ChunkMetadata


def _make_async_session() -> AsyncMock:
    """Return an AsyncMock session with synchronous add/add_all as plain MagicMock.

    SQLAlchemy's AsyncSession.add() and add_all() are synchronous methods.
    Using AsyncMock for the whole session makes them return coroutines, which
    triggers 'coroutine was never awaited' warnings when the production code
    calls them without await (correctly).
    """
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


class TestStoreAndLinkChunks:
    def _make_chunks(self, contents: list[str]) -> list[Chunk]:
        return [Chunk(content=c, metadata=ChunkMetadata(source_name="test.pdf")) for c in contents]

    async def test_all_new_chunks(self) -> None:
        """When no chunks exist in DB, all should be stored."""
        session = _make_async_session()
        store = AsyncMock(spec=ChunkStoreService)

        chunks = self._make_chunks(["chunk A", "chunk B"])

        existing_result = MagicMock()
        existing_result.all.return_value = []

        links_result = MagicMock()
        links_result.all.return_value = []

        session.exec = AsyncMock(side_effect=[existing_result])
        session.scalars = AsyncMock(return_value=links_result)

        store.store_chunks = AsyncMock(return_value=[100, 101])

        new_count, reused_count = await store_and_link_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            store=store,
        )

        assert new_count == 2
        assert reused_count == 0
        store.store_chunks.assert_awaited_once()
        call_args = store.store_chunks.call_args
        chunk_inputs = call_args[0][2]  # third positional arg
        assert len(chunk_inputs) == 2
        assert all(isinstance(ci, ChunkInput) for ci in chunk_inputs)
        assert all(ci.chunk_content_hash is not None for ci in chunk_inputs)

    async def test_all_reused_chunks(self) -> None:
        """When all chunks already exist, none should be stored."""
        session = _make_async_session()
        store = AsyncMock(spec=ChunkStoreService)

        chunks = self._make_chunks(["chunk A"])
        chunk_hash = hashlib.sha256("chunk A".encode()).hexdigest()

        existing_result = MagicMock()
        existing_result.all.return_value = [(50, chunk_hash)]

        links_result = MagicMock()
        links_result.all.return_value = []

        session.exec = AsyncMock(side_effect=[existing_result])
        session.scalars = AsyncMock(return_value=links_result)
        store.store_chunks = AsyncMock(return_value=[])

        new_count, reused_count = await store_and_link_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            store=store,
        )

        assert new_count == 0
        assert reused_count == 1
        store.store_chunks.assert_awaited_once()
        call_args = store.store_chunks.call_args
        assert call_args[0][2] == []

    async def test_mixed_new_and_reused(self) -> None:
        """When some chunks exist and some don't."""
        session = _make_async_session()
        store = AsyncMock(spec=ChunkStoreService)

        chunks = self._make_chunks(["existing chunk", "new chunk"])
        existing_hash = hashlib.sha256("existing chunk".encode()).hexdigest()

        existing_result = MagicMock()
        existing_result.all.return_value = [(50, existing_hash)]

        links_result = MagicMock()
        links_result.all.return_value = []

        session.exec = AsyncMock(side_effect=[existing_result])
        session.scalars = AsyncMock(return_value=links_result)

        store.store_chunks = AsyncMock(return_value=[51])

        new_count, reused_count = await store_and_link_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            store=store,
        )

        assert new_count == 1
        assert reused_count == 1
        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        link_chunk_ids = {link.chunk_id for link in added_links}
        assert link_chunk_ids == {50, 51}

    async def test_skips_already_linked_chunks(self) -> None:
        """Bridge-link rows that already exist should not be re-inserted."""
        session = _make_async_session()
        store = AsyncMock(spec=ChunkStoreService)

        chunks = self._make_chunks(["chunk A", "chunk B"])
        hash_a = hashlib.sha256("chunk A".encode()).hexdigest()
        hash_b = hashlib.sha256("chunk B".encode()).hexdigest()

        existing_result = MagicMock()
        existing_result.all.return_value = [(10, hash_a), (11, hash_b)]

        links_result = MagicMock()
        links_result.all.return_value = [10]

        session.exec = AsyncMock(side_effect=[existing_result])
        session.scalars = AsyncMock(return_value=links_result)
        store.store_chunks = AsyncMock(return_value=[])

        new_count, reused_count = await store_and_link_chunks(
            session,
            user_id=1,
            drive_file_id=5,
            chunks=chunks,
            store=store,
        )

        assert new_count == 0
        assert reused_count == 2
        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        assert len(added_links) == 1
        assert added_links[0].chunk_id == 11

    @pytest.mark.asyncio
    async def test_deleted_file_chunks_not_reused(self, session: AsyncSession) -> None:
        """Chunks linked only to deleted DriveFiles must never be reused."""
        from app.models.drive import DriveFile, DriveFolder
        from app.models.user import User

        async_session: AsyncSession = session

        user = User(name="ReuseTest", username="reusetest", email="reuse@test.com", hashed_password="x")
        async_session.add(user)
        await async_session.flush()

        assert user.id is not None
        folder = DriveFolder(
            user_id=user.id,
            drive_folder_id="folder_reuse",
            drive_folder_name="Reuse Folder",
            last_synced_at=datetime.now(timezone.utc),
            sync_status="synced",
        )
        async_session.add(folder)
        await async_session.flush()

        assert folder.id is not None
        new_drive_file = DriveFile(
            folder_id=folder.id,
            user_id=user.id,
            drive_file_id="new_file_id",
            name="new.pdf",
            last_synced_at=datetime.now(timezone.utc),
        )
        async_session.add(new_drive_file)
        await async_session.flush()

        deleted_drive_file = DriveFile(
            folder_id=folder.id,
            user_id=user.id,
            drive_file_id="deleted_file_id",
            name="deleted.pdf",
            last_synced_at=datetime.now(timezone.utc),
            is_deleted=True,
        )
        async_session.add(deleted_drive_file)
        await async_session.flush()

        chunk_content = "some shared chunk content"
        chunk_hash = hashlib.sha256(chunk_content.encode()).hexdigest()

        existing_chunk = DocumentChunk(
            user_id=user.id,
            source_name="deleted.pdf",
            content=chunk_content,
            chunk_content_hash=chunk_hash,
        )
        async_session.add(existing_chunk)
        await async_session.flush()

        assert deleted_drive_file.id is not None
        assert existing_chunk.id is not None
        link = DriveFileChunkLink(drive_file_id=deleted_drive_file.id, chunk_id=existing_chunk.id)
        async_session.add(link)
        await async_session.flush()

        store = AsyncMock(spec=ChunkStoreService)
        store.store_chunks = AsyncMock(return_value=[999])  # fake new chunk ID

        assert new_drive_file.id is not None
        new_count, reused_count = await store_and_link_chunks(
            async_session,
            user_id=user.id,
            drive_file_id=new_drive_file.id,
            chunks=[Chunk(content=chunk_content, metadata=ChunkMetadata(source_name="new.pdf"))],
            store=store,
        )

        assert reused_count == 0, "chunk linked only to a deleted file must not be reused"
        assert new_count == 1, "chunk must be re-stored since its only source is deleted"
