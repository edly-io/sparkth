"""Tests for Google Drive RAG pipeline utilities."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core_plugins.googledrive.exceptions import GoogleDriveAPIError
from app.core_plugins.googledrive.utils import (
    _download_file,
    _find_duplicate_file,
    _link_chunks_from_duplicate,
    _process_single_file,
    _resolve_filename,
    _set_rag_status,
    process_folder_rag,
)
from app.lib.rag import RagStatus
from app.models.drive import DriveFile, DriveFolder


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
        mock_result.first.return_value = None
        session.exec = AsyncMock(return_value=mock_result)

        drive_file = _make_drive_file()
        result = await _find_duplicate_file(session, user_id=1, drive_file=drive_file, content_hash="abc123")

        assert result is None
        session.exec.assert_awaited_once()

    async def test_returns_duplicate_when_found(self) -> None:
        duplicate = _make_drive_file(file_id=99, name="duplicate.pdf")
        session = _make_async_session()
        mock_result = MagicMock()
        mock_result.first.return_value = duplicate
        session.exec = AsyncMock(return_value=mock_result)

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
        source_result.all.return_value = [1, 2, 3]

        # Target file already has chunk 1
        target_result = MagicMock()
        target_result.all.return_value = [1]

        session.scalars = AsyncMock(side_effect=[source_result, target_result])

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
        source_result.all.return_value = [1, 2]

        target_result = MagicMock()
        target_result.all.return_value = [1, 2]

        session.scalars = AsyncMock(side_effect=[source_result, target_result])

        await _link_chunks_from_duplicate(session, drive_file_id=10, source_file_id=20)

        session.add_all.assert_not_called()
        session.flush.assert_not_awaited()

    async def test_links_all_when_none_exist(self) -> None:
        session = _make_async_session()

        source_result = MagicMock()
        source_result.all.return_value = [5, 6]

        target_result = MagicMock()
        target_result.all.return_value = []

        session.scalars = AsyncMock(side_effect=[source_result, target_result])

        await _link_chunks_from_duplicate(session, drive_file_id=10, source_file_id=20)

        session.add_all.assert_called_once()
        added_links = session.add_all.call_args[0][0]
        assert len(added_links) == 2


# ---------------------------------------------------------------------------
# _process_single_file
# ---------------------------------------------------------------------------


class TestProcessSingleFile:
    @pytest.mark.asyncio
    async def test_unsupported_file_marks_ready(self) -> None:
        from app.lib.rag import UnsupportedFileTypeError

        drive_file = _make_drive_file(name="image.png", mime_type="image/png")
        session = _make_async_session()
        with (
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
            patch("app.core_plugins.googledrive.utils._find_duplicate_file", new=AsyncMock(return_value=None)),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(side_effect=UnsupportedFileTypeError("nope")),
            ),
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)
        assert drive_file.rag_status == RagStatus.READY
        assert drive_file.rag_error is None

    @pytest.mark.asyncio
    async def test_scanned_pdf_marks_failed_with_user_message(self) -> None:
        from app.lib.rag import ScannedPDFError

        drive_file = _make_drive_file(name="scan.pdf", mime_type="application/pdf")
        session = _make_async_session()
        with (
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
            patch("app.core_plugins.googledrive.utils._find_duplicate_file", new=AsyncMock(return_value=None)),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(side_effect=ScannedPDFError("scan.pdf")),
            ),
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)
        assert drive_file.rag_status == RagStatus.FAILED
        assert drive_file.rag_error == ScannedPDFError.USER_MESSAGE

    @pytest.mark.asyncio
    async def test_new_file_full_pipeline_marks_ready(self) -> None:
        from app.lib.rag import IngestionResult

        drive_file = _make_drive_file(name="doc.pdf", mime_type="application/pdf")
        session = _make_async_session()
        with (
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
            patch("app.core_plugins.googledrive.utils._find_duplicate_file", new=AsyncMock(return_value=None)),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(return_value=IngestionResult(new_chunks=3, reused_chunks=1)),
            ) as mock_ingest,
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)
        assert drive_file.rag_status == RagStatus.READY
        mock_ingest.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_none_id_returns_early(self) -> None:
        drive_file = _make_drive_file(name="doc.pdf", mime_type="application/pdf")
        drive_file.id = None
        session = _make_async_session()
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)
        session.commit.assert_not_called()
        assert drive_file.rag_status is None

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

        file_bytes = b"duplicate content"
        mock_download.return_value = file_bytes

        duplicate = _make_drive_file(file_id=99, name="original.pdf")
        mock_find_dup.return_value = duplicate

        drive_file = _make_drive_file(name="copy.pdf")

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.READY
        assert drive_file.content_hash == hashlib.sha256(file_bytes).hexdigest()
        mock_link.assert_awaited_once()

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_drive_api_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """GoogleDriveAPIError should mark the file as failed."""
        session = _make_async_session()
        mock_download.side_effect = GoogleDriveAPIError(500, "Server Error")

        drive_file = _make_drive_file(name="failing.pdf")

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_value_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """ValueError (e.g. unsupported file type in extraction) should mark failed."""
        session = _make_async_session()
        mock_download.side_effect = ValueError("Unsupported file type")

        drive_file = _make_drive_file(name="bad.pdf")

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_google_doc_filename_resolved(self, mock_download: AsyncMock) -> None:
        """Google Docs should have .pdf appended when passed to ingest_document."""
        from app.lib.rag import IngestionResult

        session = _make_async_session()
        mock_download.return_value = b"content"

        drive_file = _make_drive_file(
            name="My Doc",
            mime_type="application/vnd.google-apps.document",
        )

        with (
            patch("app.core_plugins.googledrive.utils._find_duplicate_file", return_value=None),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
            patch("app.core_plugins.googledrive.utils.ingest_document") as mock_ingest,
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            mock_ingest.return_value = IngestionResult(new_chunks=1, reused_chunks=0)
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        # ingest_document should be called with .pdf filename
        mock_ingest.assert_awaited_once()
        assert mock_ingest.call_args.kwargs["filename"] == "My Doc.pdf"

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_integrity_error_rollback_refresh_mark_failed(self, mock_download: AsyncMock) -> None:
        """IntegrityError triggers rollback → refresh → FAILED."""
        from sqlalchemy.exc import IntegrityError

        session = _make_async_session()

        mock_download.side_effect = IntegrityError(None, None, Exception("unique violation"))

        drive_file = _make_drive_file(name="dup.pdf")

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        session.rollback.assert_awaited_once()
        # session.refresh.assert_awaited_once_with(drive_file)
        session.refresh.assert_has_awaits([call(drive_file), call(drive_file)])
        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_sqlalchemy_error_marks_failed(self, mock_download: AsyncMock) -> None:
        """SQLAlchemyError during processing sets FAILED status."""
        session = _make_async_session()

        mock_download.side_effect = SQLAlchemyError("db connection lost")

        drive_file = _make_drive_file(name="err.pdf")

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            with pytest.raises(SQLAlchemyError):
                await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.FAILED

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_size_guard_drive_reported_marks_failed(self, mock_download: AsyncMock) -> None:
        """Drive-reported size exceeding limit should set FAILED without downloading."""
        session = _make_async_session()
        drive_file = _make_drive_file(name="huge.pdf")
        drive_file.size = 200 * 1024 * 1024  # 200 MB

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.FAILED
        assert drive_file.rag_error is not None
        assert "too large" in drive_file.rag_error
        mock_download.assert_not_awaited()

    @patch("app.core_plugins.googledrive.utils._download_file")
    async def test_size_guard_post_download_marks_failed(self, mock_download: AsyncMock) -> None:
        """Post-download size check: file bytes exceeding limit should set FAILED."""
        session = _make_async_session()
        drive_file = _make_drive_file(name="big.pdf")
        # No Drive-reported size so it falls through to post-download check
        drive_file.size = None
        # Return oversized content
        mock_download.return_value = b"x" * (60 * 1024 * 1024)  # 60 MB

        with patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings:
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
            await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

        assert drive_file.rag_status == RagStatus.FAILED
        assert drive_file.rag_error is not None
        assert "too large" in drive_file.rag_error


# ---------------------------------------------------------------------------
# process_folder_rag
# ---------------------------------------------------------------------------


class TestProcessFolderRag:
    @patch("app.core_plugins.googledrive.utils.session_scope")
    async def test_skips_when_no_files(self, mock_session_cls: MagicMock) -> None:
        """Empty folder should return early."""
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        mock_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.first.return_value = folder
        files_result = MagicMock()
        files_result.all.return_value = []
        mock_session.exec = AsyncMock(side_effect=[folder_result, files_result])
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await process_folder_rag(1, user_id=1, access_token="tok")
        # Returns early without processing any files

    @patch("app.core_plugins.googledrive.utils._process_single_file")
    @patch("app.core_plugins.googledrive.utils.session_scope")
    async def test_skips_ready_files(
        self,
        mock_session_cls: MagicMock,
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
        folder_result.first.return_value = folder
        files_result = MagicMock()
        files_result.all.return_value = [ready_file, processing_file, pending_file]
        list_session.exec = AsyncMock(side_effect=[folder_result, files_result])

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
    @patch("app.core_plugins.googledrive.utils.session_scope")
    async def test_base_exception_from_gather_is_logged(
        self,
        mock_session_cls: MagicMock,
        mock_process: AsyncMock,
    ) -> None:
        """BaseException raised inside a gather task must be logged, not re-raised."""
        pending_file = _make_drive_file(file_id=1, rag_status=None)
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        list_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.first.return_value = folder
        files_result = MagicMock()
        files_result.all.return_value = [pending_file]
        list_session.exec = AsyncMock(side_effect=[folder_result, files_result])

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
