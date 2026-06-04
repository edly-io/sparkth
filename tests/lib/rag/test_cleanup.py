"""Tests for RAG cleanup: orphaned chunk deletion."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lib.rag.cleanup import cleanup_deleted_files


def _make_session(
    scalars_side_effects: list[MagicMock],
    execute_side_effects: list[MagicMock] | None = None,
) -> AsyncMock:
    """Build a mock AsyncSession.

    scalars() handles single-column SELECT queries; execute() handles DELETE/DML statements.
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.scalars = AsyncMock(side_effect=scalars_side_effects)
    session.execute = AsyncMock(side_effect=execute_side_effects or [])
    session.commit = AsyncMock()
    return session


def _rows(*values: object) -> MagicMock:
    """Return a mock result whose .all() yields scalar values."""
    result = MagicMock()
    result.all.return_value = list(values)
    return result


@pytest.fixture
def patch_session() -> Generator[MagicMock, None, None]:
    """Patch session_scope so cleanup_deleted_files uses our mock."""
    with patch("app.lib.rag.cleanup.session_scope") as mock_cls:
        yield mock_cls


class TestCleanupDeletedFiles:
    async def test_no_deleted_files_exits_early(self, patch_session: MagicMock) -> None:
        session = _make_session([_rows()])  # empty deleted-files result
        patch_session.return_value = session

        await cleanup_deleted_files()

        session.scalars.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_duplicate_files_with_no_chunks_are_deleted(self, patch_session: MagicMock) -> None:
        """Deleted drive files with no chunks (duplicates) are still hard-deleted."""
        session = _make_session(
            scalars_side_effects=[_rows(1, 2), _rows()],  # deleted ids, no candidate chunks
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.scalars.await_count == 2
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_all_chunks_still_alive_deletes_files_only(self, patch_session: MagicMock) -> None:
        """When all chunks are still alive, delete file links and files but not chunks."""
        session = _make_session(
            scalars_side_effects=[
                _rows(1),
                _rows(10, 11),
                _rows(10, 11),
            ],  # deleted ids, candidates, alive (no orphans)
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_orphaned_chunks_are_deleted(self, patch_session: MagicMock) -> None:
        session = _make_session(
            scalars_side_effects=[
                _rows(1),
                _rows(10, 11),
                _rows(10),
            ],  # deleted ids, candidates, alive → chunk 11 orphaned
            execute_side_effects=[MagicMock(), MagicMock(), MagicMock()],  # DELETE links, DELETE chunks, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 3
        session.commit.assert_awaited_once()

    async def test_all_chunks_orphaned_when_no_alive_files(self, patch_session: MagicMock) -> None:
        session = _make_session(
            scalars_side_effects=[_rows(1, 2), _rows(10, 11, 12), _rows()],  # deleted ids, candidates, no alive
            execute_side_effects=[MagicMock(), MagicMock(), MagicMock()],  # DELETE links, DELETE chunks, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 3
        session.commit.assert_awaited_once()

    async def test_shared_chunk_preserved_when_one_file_alive(self, patch_session: MagicMock) -> None:
        """Chunk linked to both a deleted and a live file must not be deleted."""
        session = _make_session(
            scalars_side_effects=[_rows(1), _rows(99), _rows(99)],  # deleted ids, candidates, chunk 99 also alive
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_delete_statements_use_correct_ids(self, patch_session: MagicMock) -> None:
        """DELETE statements reference the right file/chunk ids."""
        session = _make_session(
            scalars_side_effects=[
                _rows(5),
                _rows(20, 21),
                _rows(20),
            ],  # deleted id, candidates, chunk 20 alive → 21 orphaned
            execute_side_effects=[MagicMock(), MagicMock(), MagicMock()],  # DELETE links, DELETE chunks, DELETE files
        )
        patch_session.return_value = session

        await cleanup_deleted_files()

        calls = session.execute.await_args_list
        compiled_links = str(calls[0][0][0].compile(compile_kwargs={"literal_binds": False}))
        compiled_chunks = str(calls[1][0][0].compile(compile_kwargs={"literal_binds": False}))
        compiled_files = str(calls[2][0][0].compile(compile_kwargs={"literal_binds": False}))

        assert "rag_drive_file_chunk_links" in compiled_links
        assert "rag_document_chunks" in compiled_chunks
        assert "drive_files" in compiled_files
