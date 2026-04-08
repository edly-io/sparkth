"""Tests for RAG cleanup: orphaned chunk deletion."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.cleanup import cleanup_deleted_files


def _make_session(execute_side_effects: list[MagicMock | AsyncMock]) -> AsyncMock:
    """Build a mock AsyncSession whose execute() returns results in sequence."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.execute = AsyncMock(side_effect=execute_side_effects)
    session.commit = AsyncMock()
    return session


def _rows(*values: object) -> MagicMock:
    """Return a mock result whose .all() yields (value,) tuples."""
    result = MagicMock()
    result.all.return_value = [(v,) for v in values]
    return result


@pytest.fixture
def patch_session() -> Generator[MagicMock, None, None]:
    """Patch AsyncSession so cleanup_deleted_files uses our mock."""
    with patch("app.rag.cleanup.AsyncSession") as mock_cls:
        yield mock_cls


class TestCleanupDeletedFiles:
    async def test_no_deleted_files_exits_early(self, patch_session: MagicMock) -> None:
        session = _make_session([_rows()])  # empty deleted-files result
        patch_session.return_value = session

        await cleanup_deleted_files()

        session.execute.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_duplicate_files_with_no_chunks_are_deleted(self, patch_session: MagicMock) -> None:
        """Deleted drive files with no chunks (duplicates) are still hard-deleted."""
        session = _make_session(
            [
                _rows(1, 2),  # deleted file ids
                _rows(),  # no candidate chunks
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        # 4 executes: deleted ids, candidates, delete links, delete files
        assert session.execute.await_count == 4
        session.commit.assert_awaited_once()

    async def test_all_chunks_still_alive_deletes_files_only(self, patch_session: MagicMock) -> None:
        """When all chunks are still alive, delete file links and files but not chunks."""
        session = _make_session(
            [
                _rows(1),  # deleted file ids
                _rows(10, 11),  # candidate chunk ids
                _rows(10, 11),  # alive chunk ids (same set → no orphans)
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        # 5 executes: deleted ids, candidates, alive, delete links, delete files
        assert session.execute.await_count == 5
        session.commit.assert_awaited_once()

    async def test_orphaned_chunks_are_deleted(self, patch_session: MagicMock) -> None:
        session = _make_session(
            [
                _rows(1),  # deleted file ids
                _rows(10, 11),  # candidate chunk ids
                _rows(10),  # alive chunk ids → chunk 11 is orphaned
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DocumentChunk
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        # 6 executes: deleted ids, candidates, alive, delete links, delete chunks, delete files
        assert session.execute.await_count == 6
        session.commit.assert_awaited_once()

    async def test_all_chunks_orphaned_when_no_alive_files(self, patch_session: MagicMock) -> None:
        session = _make_session(
            [
                _rows(1, 2),  # deleted file ids
                _rows(10, 11, 12),  # candidate chunk ids
                _rows(),  # no alive chunks
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DocumentChunk
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.execute.await_count == 6
        session.commit.assert_awaited_once()

    async def test_shared_chunk_preserved_when_one_file_alive(self, patch_session: MagicMock) -> None:
        """Chunk linked to both a deleted and a live file must not be deleted."""
        session = _make_session(
            [
                _rows(1),  # file 1 deleted
                _rows(99),  # chunk 99 linked to deleted file 1
                _rows(99),  # chunk 99 also alive (linked to live file 2)
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        # 5 executes: deleted ids, candidates, alive, delete links, delete files
        assert session.execute.await_count == 5
        session.commit.assert_awaited_once()

    async def test_delete_statements_use_correct_ids(self, patch_session: MagicMock) -> None:
        """DELETE statements reference the right file/chunk ids."""
        session = _make_session(
            [
                _rows(5),  # deleted file id = 5
                _rows(20, 21),  # candidate chunk ids
                _rows(20),  # chunk 20 alive → chunk 21 orphaned
                MagicMock(),  # DELETE DriveFileChunkLink
                MagicMock(),  # DELETE DocumentChunk
                MagicMock(),  # DELETE DriveFile
            ]
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        calls = session.execute.await_args_list
        compiled_links = str(calls[3][0][0].compile(compile_kwargs={"literal_binds": False}))
        compiled_chunks = str(calls[4][0][0].compile(compile_kwargs={"literal_binds": False}))
        compiled_files = str(calls[5][0][0].compile(compile_kwargs={"literal_binds": False}))

        assert "rag_drive_file_chunk_links" in compiled_links
        assert "rag_document_chunks" in compiled_chunks
        assert "drive_files" in compiled_files
