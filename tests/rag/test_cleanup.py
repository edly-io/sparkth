"""Tests for RAG cleanup: orphaned chunk deletion."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.cleanup import cleanup_deleted_documents


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
    """Patch session_scope so cleanup_deleted_documents uses our mock."""
    with patch("app.rag.cleanup.session_scope") as mock_cls:
        yield mock_cls


class TestCleanupDeletedDocuments:
    async def test_no_deleted_documents_exits_early(self, patch_session: MagicMock) -> None:
        session = _make_session([_rows()])  # empty deleted-documents result
        patch_session.return_value = session

        await cleanup_deleted_documents()

        session.scalars.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_deleted_documents_with_no_chunks(self, patch_session: MagicMock) -> None:
        """Deleted Documents with no linked chunks: only delete links (0 rows matched)."""
        session = _make_session(
            scalars_side_effects=[_rows(1, 2), _rows()],  # deleted doc ids, no candidate chunks
            execute_side_effects=[MagicMock()],  # DELETE links only
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        assert session.scalars.await_count == 2
        assert session.execute.await_count == 1
        session.commit.assert_awaited_once()

    async def test_all_chunks_still_alive_deletes_links_only(self, patch_session: MagicMock) -> None:
        """When all chunks are still alive, delete only document-chunk links."""
        session = _make_session(
            scalars_side_effects=[
                _rows(1),
                _rows(10, 11),
                _rows(10, 11),  # all chunks are alive
            ],
            execute_side_effects=[MagicMock()],  # DELETE links only
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 1
        session.commit.assert_awaited_once()

    async def test_orphaned_chunks_are_deleted(self, patch_session: MagicMock) -> None:
        session = _make_session(
            scalars_side_effects=[
                _rows(1),
                _rows(10, 11),
                _rows(10),  # chunk 11 orphaned
            ],
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE chunks
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_all_chunks_orphaned_when_no_alive_documents(self, patch_session: MagicMock) -> None:
        session = _make_session(
            scalars_side_effects=[_rows(1, 2), _rows(10, 11, 12), _rows()],  # deleted ids, candidates, none alive
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE chunks
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 2
        session.commit.assert_awaited_once()

    async def test_shared_chunk_preserved_when_one_document_alive(self, patch_session: MagicMock) -> None:
        """Chunk linked to both a deleted and a live document must not be deleted."""
        session = _make_session(
            scalars_side_effects=[_rows(1), _rows(99), _rows(99)],  # chunk 99 also alive
            execute_side_effects=[MagicMock()],  # DELETE links only
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        assert session.scalars.await_count == 3
        assert session.execute.await_count == 1
        session.commit.assert_awaited_once()

    async def test_delete_statements_use_correct_ids(self, patch_session: MagicMock) -> None:
        """DELETE statements reference the right document/chunk ids."""
        session = _make_session(
            scalars_side_effects=[
                _rows(5),
                _rows(20, 21),
                _rows(20),  # chunk 21 orphaned
            ],
            execute_side_effects=[MagicMock(), MagicMock()],  # DELETE links, DELETE chunks
        )
        patch_session.return_value = session

        await cleanup_deleted_documents()

        calls = session.execute.await_args_list
        compiled_links = str(calls[0][0][0].compile(compile_kwargs={"literal_binds": False}))
        compiled_chunks = str(calls[1][0][0].compile(compile_kwargs={"literal_binds": False}))

        assert "rag_document_chunk_links" in compiled_links
        assert "rag_document_chunks" in compiled_chunks
