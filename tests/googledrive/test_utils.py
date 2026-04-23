"""Tests for Google Drive RAG pipeline utilities."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core_plugins.googledrive.client import GoogleDriveAPIError
from app.core_plugins.googledrive.utils import (
    _download_file,
    _embed_and_store_chunks,
    _find_duplicate_file,
    _is_supported_for_rag,
    _link_chunks_from_duplicate,
    _process_single_file,
    _resolve_filename,
    _set_rag_status,
    process_folder_rag,
)
from app.models.drive import DriveFile, DriveFolder
from app.rag.store import ChunkInput, VectorStoreService
from app.rag.types import Chunk, ChunkMetadata, RagStatus


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


def _make_drive_file(
    *,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    rag_status: RagStatus | None = None,
    content_hash: str | None = None,
    file_id: int = 1,
    user_id: int = 1,
    folder_id: int = 1,
) -> DriveFile:
    """Create a DriveFile instance for testing."""
    f = DriveFile(
        id=file_id,
        folder_id=folder_id,
        user_id=user_id,
        drive_file_id=f"drive_{file_id}",
        name=name,
        mime_type=mime_type,
        rag_status=rag_status,
        content_hash=content_hash,
    )
    return f


# ---------------------------------------------------------------------------
# _resolve_filename
# ---------------------------------------------------------------------------


class TestResolveFilename:
    def test_regular_pdf(self) -> None:
        f = _make_drive_file(name="report.pdf", mime_type="application/pdf")
        assert _resolve_filename(f) == "report.pdf"

    def test_regular_docx(self) -> None:
        f = _make_drive_file(
            name="notes.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert _resolve_filename(f) == "notes.docx"

    def test_google_doc_gets_pdf_suffix(self) -> None:
        f = _make_drive_file(name="My Google Doc", mime_type="application/vnd.google-apps.document")
        assert _resolve_filename(f) == "My Google Doc.pdf"

    def test_google_sheet_gets_pdf_suffix(self) -> None:
        f = _make_drive_file(name="Spreadsheet", mime_type="application/vnd.google-apps.spreadsheet")
        assert _resolve_filename(f) == "Spreadsheet.pdf"

    def test_google_slides_gets_pdf_suffix(self) -> None:
        f = _make_drive_file(name="Presentation", mime_type="application/vnd.google-apps.presentation")
        assert _resolve_filename(f) == "Presentation.pdf"

    def test_google_doc_already_has_pdf_suffix(self) -> None:
        f = _make_drive_file(name="Already.pdf", mime_type="application/vnd.google-apps.document")
        assert _resolve_filename(f) == "Already.pdf"

    def test_google_doc_pdf_suffix_case_insensitive(self) -> None:
        f = _make_drive_file(name="Already.PDF", mime_type="application/vnd.google-apps.document")
        assert _resolve_filename(f) == "Already.PDF"

    def test_none_mime_type(self) -> None:
        f = _make_drive_file(name="mystery.bin", mime_type=None)
        assert _resolve_filename(f) == "mystery.bin"


# ---------------------------------------------------------------------------
# _is_supported_for_rag
# ---------------------------------------------------------------------------


class TestIsSupportedForRag:
    @pytest.mark.parametrize(
        "filename",
        ["report.pdf", "notes.docx", "page.html", "page.htm", "readme.txt", "notes.md"],
    )
    def test_supported_extensions(self, filename: str) -> None:
        assert _is_supported_for_rag(filename) is True

    @pytest.mark.parametrize(
        "filename",
        ["image.png", "photo.jpg", "video.mp4", "archive.zip", "data.csv", "sheet.xlsx"],
    )
    def test_unsupported_extensions(self, filename: str) -> None:
        assert _is_supported_for_rag(filename) is False

    def test_case_insensitive(self) -> None:
        assert _is_supported_for_rag("REPORT.PDF") is True
        assert _is_supported_for_rag("Notes.DOCX") is True

    def test_no_extension(self) -> None:
        assert _is_supported_for_rag("README") is False

    def test_double_extension_uses_last(self) -> None:
        assert _is_supported_for_rag("file.backup.pdf") is True
        assert _is_supported_for_rag("file.pdf.bak") is False


# ---------------------------------------------------------------------------
# _set_rag_status
# ---------------------------------------------------------------------------


class TestSetRagStatus:
    async def test_updates_status_and_commits(self) -> None:
        session = _make_async_session()
        drive_file = _make_drive_file()
        original_updated_at = drive_file.updated_at

        await _set_rag_status(session, drive_file, RagStatus.PROCESSING)

        assert drive_file.rag_status == RagStatus.PROCESSING
        assert drive_file.updated_at >= original_updated_at
        session.add.assert_called_once_with(drive_file)
        session.commit.assert_awaited_once()

    async def test_sets_ready_status(self) -> None:
        session = _make_async_session()
        drive_file = _make_drive_file(rag_status=RagStatus.PROCESSING)

        await _set_rag_status(session, drive_file, RagStatus.READY)

        assert drive_file.rag_status == RagStatus.READY

    async def test_sets_failed_status(self) -> None:
        session = _make_async_session()
        drive_file = _make_drive_file(rag_status=RagStatus.PROCESSING)

        await _set_rag_status(session, drive_file, RagStatus.FAILED)

        assert drive_file.rag_status == RagStatus.FAILED


# ---------------------------------------------------------------------------
# _download_file
# ---------------------------------------------------------------------------


class TestDownloadFile:
    async def test_downloads_with_correct_params(self) -> None:
        drive_file = _make_drive_file(mime_type="application/pdf")
        expected_bytes = b"PDF content here"

        with patch("app.core_plugins.googledrive.utils.GoogleDriveClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.download_file.return_value = expected_bytes
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await _download_file("fake_token", drive_file)

        assert result == expected_bytes
        mock_client.download_file.assert_awaited_once_with(
            drive_file.drive_file_id,
            mime_type="application/pdf",
        )


# ---------------------------------------------------------------------------
# _find_duplicate_file
# ---------------------------------------------------------------------------


class TestFindDuplicateFile:
    async def test_returns_none_when_no_duplicate(self) -> None:
        session = _make_async_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        drive_file = _make_drive_file()
        result = await _find_duplicate_file(session, user_id=1, drive_file=drive_file, content_hash="abc123")

        assert result is None
        session.execute.assert_awaited_once()

    async def test_returns_duplicate_when_found(self) -> None:
        duplicate = _make_drive_file(file_id=99, name="duplicate.pdf")
        session = _make_async_session()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = duplicate
        session.execute = AsyncMock(return_value=mock_result)

        drive_file = _make_drive_file()
        result = await _find_duplicate_file(session, user_id=1, drive_file=drive_file, content_hash="abc123")

        assert result is duplicate


# ---------------------------------------------------------------------------
# _link_chunks_from_duplicate
# ---------------------------------------------------------------------------


class TestLinkChunksFromDuplicate:
    async def test_links_missing_chunks(self) -> None:
        session = _make_async_session()

        # Source file has chunks 1, 2, 3
        source_result = MagicMock()
        source_result.all.return_value = [(1,), (2,), (3,)]

        # Target file already has chunk 1
        target_result = MagicMock()
        target_result.all.return_value = [(1,)]

        session.execute = AsyncMock(side_effect=[source_result, target_result])

        await _link_chunks_from_duplicate(session, drive_file_id=10, source_file_id=20)

        # Should add links for chunks 2 and 3 only
        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        added_chunk_ids = {link.chunk_id for link in added_links}
        assert added_chunk_ids == {2, 3}
        session.flush.assert_awaited_once()

    async def test_no_links_when_all_exist(self) -> None:
        session = _make_async_session()

        source_result = MagicMock()
        source_result.all.return_value = [(1,), (2,)]

        target_result = MagicMock()
        target_result.all.return_value = [(1,), (2,)]

        session.execute = AsyncMock(side_effect=[source_result, target_result])

        await _link_chunks_from_duplicate(session, drive_file_id=10, source_file_id=20)

        session.add_all.assert_not_called()
        session.flush.assert_not_awaited()

    async def test_links_all_when_none_exist(self) -> None:
        session = _make_async_session()

        source_result = MagicMock()
        source_result.all.return_value = [(5,), (6,)]

        target_result = MagicMock()
        target_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[source_result, target_result])

        await _link_chunks_from_duplicate(session, drive_file_id=10, source_file_id=20)

        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        assert len(added_links) == 2


# ---------------------------------------------------------------------------
# _embed_and_store_chunks
# ---------------------------------------------------------------------------


class TestEmbedAndStoreChunks:
    def _make_chunks(self, contents: list[str]) -> list[Chunk]:
        return [Chunk(content=c, metadata=ChunkMetadata(source_name="test.pdf")) for c in contents]

    async def test_all_new_chunks(self) -> None:
        """When no chunks exist in DB, all should be embedded."""
        session = _make_async_session()
        provider = AsyncMock(spec=True)
        store = AsyncMock(spec=VectorStoreService)

        chunks = self._make_chunks(["chunk A", "chunk B"])

        # No existing chunks in DB
        existing_result = MagicMock()
        existing_result.all.return_value = []

        # No existing links
        links_result = MagicMock()
        links_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[existing_result, links_result])

        row1 = MagicMock(id=100)
        row2 = MagicMock(id=101)
        store.store_chunks = AsyncMock(return_value=[row1, row2])

        new_count, reused_count = await _embed_and_store_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            provider=provider,
            store=store,
        )

        assert new_count == 2
        assert reused_count == 0
        store.store_chunks.assert_awaited_once()
        # Verify ChunkInputs were passed
        call_args = store.store_chunks.call_args
        chunk_inputs = call_args[0][2]  # third positional arg
        assert len(chunk_inputs) == 2
        assert all(isinstance(ci, ChunkInput) for ci in chunk_inputs)
        assert all(ci.chunk_content_hash is not None for ci in chunk_inputs)

    async def test_all_reused_chunks(self) -> None:
        """When all chunks already exist, none should be embedded."""
        session = _make_async_session()
        provider = AsyncMock(spec=True)
        store = AsyncMock(spec=VectorStoreService)

        chunks = self._make_chunks(["chunk A"])
        chunk_hash = hashlib.sha256("chunk A".encode()).hexdigest()

        # One existing chunk with matching hash
        existing_row = MagicMock()
        existing_row.chunk_content_hash = chunk_hash
        existing_row.id = 50
        existing_result = MagicMock()
        existing_result.all.return_value = [existing_row]

        # No existing links
        links_result = MagicMock()
        links_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[existing_result, links_result])
        store.store_chunks = AsyncMock(return_value=[])

        new_count, reused_count = await _embed_and_store_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            provider=provider,
            store=store,
        )

        assert new_count == 0
        assert reused_count == 1
        # store_chunks called with empty list
        store.store_chunks.assert_awaited_once()
        call_args = store.store_chunks.call_args
        assert call_args[0][2] == []

    async def test_mixed_new_and_reused(self) -> None:
        """When some chunks exist and some don't."""
        session = _make_async_session()
        provider = AsyncMock(spec=True)
        store = AsyncMock(spec=VectorStoreService)

        chunks = self._make_chunks(["existing chunk", "new chunk"])
        existing_hash = hashlib.sha256("existing chunk".encode()).hexdigest()

        existing_row = MagicMock()
        existing_row.chunk_content_hash = existing_hash
        existing_row.id = 50
        existing_result = MagicMock()
        existing_result.all.return_value = [existing_row]

        links_result = MagicMock()
        links_result.all.return_value = []

        session.execute = AsyncMock(side_effect=[existing_result, links_result])

        new_row = MagicMock(id=51)
        store.store_chunks = AsyncMock(return_value=[new_row])

        new_count, reused_count = await _embed_and_store_chunks(
            session,
            user_id=1,
            drive_file_id=10,
            chunks=chunks,
            provider=provider,
            store=store,
        )

        assert new_count == 1
        assert reused_count == 1
        # Bridge links created for both
        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        link_chunk_ids = {link.chunk_id for link in added_links}
        assert link_chunk_ids == {50, 51}

    async def test_skips_already_linked_chunks(self) -> None:
        """Bridge-link rows that already exist should not be re-inserted."""
        session = _make_async_session()
        provider = AsyncMock(spec=True)
        store = AsyncMock(spec=VectorStoreService)

        chunks = self._make_chunks(["chunk A", "chunk B"])
        hash_a = hashlib.sha256("chunk A".encode()).hexdigest()
        hash_b = hashlib.sha256("chunk B".encode()).hexdigest()

        # Both chunks already exist in DB
        row_a = MagicMock(chunk_content_hash=hash_a, id=10)
        row_b = MagicMock(chunk_content_hash=hash_b, id=11)
        existing_result = MagicMock()
        existing_result.all.return_value = [row_a, row_b]

        # chunk 10 already linked; chunk 11 is not
        links_result = MagicMock()
        links_result.all.return_value = [(10,)]

        session.execute = AsyncMock(side_effect=[existing_result, links_result])
        store.store_chunks = AsyncMock(return_value=[])

        new_count, reused_count = await _embed_and_store_chunks(
            session,
            user_id=1,
            drive_file_id=5,
            chunks=chunks,
            provider=provider,
            store=store,
        )

        assert new_count == 0
        assert reused_count == 2
        # Only chunk 11 should be newly linked
        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        assert len(added_links) == 1
        assert added_links[0].chunk_id == 11


# ---------------------------------------------------------------------------
# _process_single_file
# ---------------------------------------------------------------------------


class TestProcessSingleFile:
    async def test_skips_unsupported_file(self) -> None:
        """Unsupported files should be set to READY so polling stops."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()
        drive_file = _make_drive_file(name="image.png", mime_type="image/png")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.READY
        session.commit.assert_awaited()

    @patch("app.core_plugins.googledrive.utils._download_file")
    @patch("app.core_plugins.googledrive.utils._find_duplicate_file")
    @patch("app.core_plugins.googledrive.utils._link_chunks_from_duplicate")
    async def test_duplicate_file_links_and_marks_ready(
        self,
        mock_link: AsyncMock,
        mock_find_dup: AsyncMock,
        mock_download: AsyncMock,
    ) -> None:
        """Duplicate files should link to existing chunks and be marked ready."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        file_bytes = b"duplicate content"
        mock_download.return_value = file_bytes

        duplicate = _make_drive_file(file_id=99, name="original.pdf")
        mock_find_dup.return_value = duplicate

        drive_file = _make_drive_file(name="copy.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.READY
        assert drive_file.content_hash == hashlib.sha256(file_bytes).hexdigest()
        mock_link.assert_awaited_once()

    @patch("app.core_plugins.googledrive.utils._download_file")
    @patch("app.core_plugins.googledrive.utils._find_duplicate_file", return_value=None)
    @patch("app.core_plugins.googledrive.utils.extract_to_markdown")
    @patch("app.core_plugins.googledrive.utils.chunk_document")
    @patch("app.core_plugins.googledrive.utils._embed_and_store_chunks")
    async def test_new_file_full_pipeline(
        self,
        mock_embed: AsyncMock,
        mock_chunk: MagicMock,
        mock_extract: MagicMock,
        mock_find_dup: AsyncMock,
        mock_download: AsyncMock,
    ) -> None:
        """New files should go through extract -> chunk -> embed -> store."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        mock_download.return_value = b"file content"

        mock_extraction_result = MagicMock()
        mock_extract.return_value = mock_extraction_result

        chunks = [Chunk(content="chunk 1", metadata=ChunkMetadata(source_name="test.pdf"))]
        mock_chunk.return_value = chunks
        mock_embed.return_value = (1, 0)

        drive_file = _make_drive_file(name="new_doc.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.READY
        mock_extract.assert_called_once_with(b"file content", "new_doc.pdf")
        mock_chunk.assert_called_once_with(mock_extraction_result)
        mock_embed.assert_awaited_once()

    @patch("app.core_plugins.googledrive.utils._download_file")
    @patch("app.core_plugins.googledrive.utils._find_duplicate_file", return_value=None)
    @patch("app.core_plugins.googledrive.utils.extract_to_markdown")
    @patch("app.core_plugins.googledrive.utils.chunk_document", return_value=[])
    async def test_empty_chunks_marks_ready(
        self,
        mock_chunk: MagicMock,
        mock_extract: MagicMock,
        mock_find_dup: AsyncMock,
        mock_download: AsyncMock,
    ) -> None:
        """Files that produce no chunks should still be marked ready."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()
        mock_download.return_value = b"content"
        mock_extract.return_value = MagicMock()

        drive_file = _make_drive_file(name="empty.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.READY

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_drive_api_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """GoogleDriveAPIError should mark the file as failed."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()
        mock_download.side_effect = GoogleDriveAPIError(500, "Server Error")

        drive_file = _make_drive_file(name="failing.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_value_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """ValueError (e.g. unsupported file type in extraction) should mark failed."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()
        mock_download.side_effect = ValueError("Unsupported file type")

        drive_file = _make_drive_file(name="bad.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_google_doc_filename_resolved(self, mock_download: AsyncMock) -> None:
        """Google Docs should have .pdf appended for extraction."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()
        mock_download.return_value = b"content"

        drive_file = _make_drive_file(
            name="My Doc",
            mime_type="application/vnd.google-apps.document",
        )

        with (
            patch("app.core_plugins.googledrive.utils._find_duplicate_file", return_value=None),
            patch("app.core_plugins.googledrive.utils.extract_to_markdown") as mock_extract,
            patch("app.core_plugins.googledrive.utils.chunk_document", return_value=[]),
        ):
            mock_extract.return_value = MagicMock()
            await _process_single_file(
                drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
            )

        # extract_to_markdown should be called with .pdf filename
        mock_extract.assert_called_once_with(b"content", "My Doc.pdf")

    async def test_none_id_returns_early(self) -> None:
        """drive_file.id is None should log error and return without touching session."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        drive_file = _make_drive_file(name="doc.pdf")
        drive_file.id = None

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        session.commit.assert_not_awaited()
        assert drive_file.rag_status is None

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_integrity_error_rollback_refresh_mark_failed(self, mock_download: AsyncMock) -> None:
        """IntegrityError triggers rollback → refresh → FAILED."""
        from sqlalchemy.exc import IntegrityError

        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        mock_download.side_effect = IntegrityError(None, None, Exception("unique violation"))

        drive_file = _make_drive_file(name="dup.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        session.rollback.assert_awaited_once()
        session.refresh.assert_awaited_once_with(drive_file)
        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_sqlalchemy_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """SQLAlchemyError during processing sets FAILED status."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        mock_download.side_effect = SQLAlchemyError("db connection lost")

        drive_file = _make_drive_file(name="err.pdf")

        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    @patch("app.core_plugins.googledrive.utils._set_rag_status")
    async def test_set_rag_status_failure_in_sqlalchemy_fallback_is_swallowed(
        self, mock_set_status: AsyncMock, mock_download: AsyncMock
    ) -> None:
        """When _set_rag_status itself raises inside except SQLAlchemyError, error is swallowed."""
        session = _make_async_session()
        provider = AsyncMock()
        store = AsyncMock()

        mock_download.side_effect = SQLAlchemyError("db connection lost")
        # First call sets PROCESSING (succeeds), second raises
        mock_set_status.side_effect = [None, SQLAlchemyError("db gone")]

        drive_file = _make_drive_file(name="bad.pdf")

        # No exception re-raised, error is swallowed
        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=provider, store=store
        )


# ---------------------------------------------------------------------------
# process_folder_rag
# ---------------------------------------------------------------------------


class TestProcessFolderRag:
    @patch("app.core_plugins.googledrive.utils.AsyncSession")
    @patch("app.core_plugins.googledrive.utils.get_provider")
    async def test_skips_when_no_files(self, mock_provider: MagicMock, mock_session_cls: MagicMock) -> None:
        """Empty folder should return early."""
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        mock_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.scalars.return_value.first.return_value = folder
        files_result = MagicMock()
        files_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[folder_result, files_result])
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await process_folder_rag(1, user_id=1, access_token="tok")

        mock_provider.assert_not_called()

    @patch("app.core_plugins.googledrive.utils._process_single_file")
    @patch("app.core_plugins.googledrive.utils.VectorStoreService")
    @patch("app.core_plugins.googledrive.utils.get_provider")
    @patch("app.core_plugins.googledrive.utils.AsyncSession")
    async def test_skips_ready_files(
        self,
        mock_session_cls: MagicMock,
        mock_provider: MagicMock,
        mock_store_cls: MagicMock,
        mock_process: AsyncMock,
    ) -> None:
        """Files with rag_status='ready' should be skipped."""
        ready_file = _make_drive_file(file_id=1, rag_status=RagStatus.READY)
        processing_file = _make_drive_file(file_id=3, rag_status=RagStatus.PROCESSING)
        pending_file = _make_drive_file(file_id=2, rag_status=None)

        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        # First call: folder lookup + file listing session
        list_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.scalars.return_value.first.return_value = folder
        files_result = MagicMock()
        files_result.scalars.return_value.all.return_value = [ready_file, processing_file, pending_file]
        list_session.execute = AsyncMock(side_effect=[folder_result, files_result])

        # Second call: per-file processing session
        file_session = AsyncMock()

        sessions = iter([list_session, file_session])

        def make_ctx(*args: object, **kwargs: object) -> MagicMock:
            ctx = MagicMock()
            s = next(sessions)
            ctx.__aenter__ = AsyncMock(return_value=s)
            ctx.__aexit__ = AsyncMock(return_value=None)
            return ctx

        mock_session_cls.side_effect = make_ctx
        await process_folder_rag(1, user_id=1, access_token="tok")

        # Only the pending file should be processed (ready + processing skipped)
        assert mock_process.await_count == 1
        processed_file = mock_process.call_args[0][0]
        assert processed_file.id == 2

    @patch("app.core_plugins.googledrive.utils._process_single_file")
    @patch("app.core_plugins.googledrive.utils.VectorStoreService")
    @patch("app.core_plugins.googledrive.utils.get_provider")
    @patch("app.core_plugins.googledrive.utils.AsyncSession")
    async def test_base_exception_from_gather_is_logged(
        self,
        mock_session_cls: MagicMock,
        mock_provider: MagicMock,
        mock_store_cls: MagicMock,
        mock_process: AsyncMock,
    ) -> None:
        """BaseException raised inside a gather task must be logged, not re-raised."""
        pending_file = _make_drive_file(file_id=1, rag_status=None)
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        list_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.scalars.return_value.first.return_value = folder
        files_result = MagicMock()
        files_result.scalars.return_value.all.return_value = [pending_file]
        list_session.execute = AsyncMock(side_effect=[folder_result, files_result])

        file_session = AsyncMock()
        sessions = iter([list_session, file_session])

        def make_ctx(*args: object, **kwargs: object) -> MagicMock:
            ctx = MagicMock()
            s = next(sessions)
            ctx.__aenter__ = AsyncMock(return_value=s)
            ctx.__aexit__ = AsyncMock(return_value=None)
            return ctx

        mock_session_cls.side_effect = make_ctx
        mock_process.side_effect = BaseException("fatal")

        # Must not propagate
        await process_folder_rag(1, user_id=1, access_token="tok")


# ---------------------------------------------------------------------------
# _set_rag_status with error message
# ---------------------------------------------------------------------------


class TestSetRagStatusWithError:
    @pytest.mark.asyncio
    async def test_stores_error_message_on_failed(self) -> None:
        """_set_rag_status should persist rag_error when provided."""
        file = _make_drive_file()
        session = _make_async_session()

        await _set_rag_status(session, file, RagStatus.FAILED, error="Download failed: 403 Forbidden")

        assert file.rag_status == RagStatus.FAILED
        assert file.rag_error == "Download failed: 403 Forbidden"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clears_error_message_on_ready(self) -> None:
        """_set_rag_status should clear rag_error when status is not failed."""
        file = _make_drive_file(rag_status=RagStatus.FAILED)
        file.rag_error = "old error"
        session = _make_async_session()

        await _set_rag_status(session, file, RagStatus.READY)

        assert file.rag_status == RagStatus.READY
        assert file.rag_error is None
        session.commit.assert_awaited_once()
