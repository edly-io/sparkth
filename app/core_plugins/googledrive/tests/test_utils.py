"""Tests for Google Drive RAG pipeline utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.core_plugins.googledrive.exceptions import GoogleDriveAPIError
from app.core_plugins.googledrive.utils import (
    _download_file,
    _find_ready_duplicate_document_id,
    _process_single_file,
    _resolve_filename,
    process_folder_rag,
)
from app.models.drive import DriveFile, DriveFolder


def _make_async_session() -> AsyncMock:
    """Return an AsyncMock session with synchronous add/add_all as plain MagicMock."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


def _make_drive_file(
    *,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    content_hash: str | None = None,
    file_id: int = 1,
    user_id: int = 1,
    folder_id: int = 1,
    document_id: int | None = 10,
) -> DriveFile:
    f = DriveFile(
        id=file_id,
        folder_id=folder_id,
        user_id=user_id,
        drive_file_id=f"drive_{file_id}",
        name=name,
        mime_type=mime_type,
        content_hash=content_hash,
        document_id=document_id,
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
# _find_ready_duplicate_document_id
# ---------------------------------------------------------------------------


class TestFindReadyDuplicateDocumentId:
    async def test_returns_none_when_no_duplicate(self) -> None:
        session = _make_async_session()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec = AsyncMock(return_value=result_mock)
        drive_file = _make_drive_file()
        result = await _find_ready_duplicate_document_id(session, 1, drive_file, "abc123")
        assert result is None

    async def test_returns_document_id_when_found(self) -> None:
        session = _make_async_session()
        result_mock = MagicMock()
        result_mock.first.return_value = 99  # document_id
        session.exec = AsyncMock(return_value=result_mock)
        drive_file = _make_drive_file()
        result = await _find_ready_duplicate_document_id(session, 1, drive_file, "abc123")
        assert result == 99


# ---------------------------------------------------------------------------
# _process_single_file
# ---------------------------------------------------------------------------


class TestProcessSingleFile:
    async def test_registers_document_when_none(self) -> None:
        """If drive_file.document_id is None, register_document is called."""
        drive_file = _make_drive_file(document_id=None)
        session = _make_async_session()
        mock_doc = MagicMock()
        mock_doc.id = 42
        with (
            patch(
                "app.core_plugins.googledrive.utils.register_document",
                new=AsyncMock(return_value=mock_doc),
            ),
            patch("app.core_plugins.googledrive.utils.update_document_status", new=AsyncMock()),
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(return_value=MagicMock(new_chunks=1, reused_chunks=0)),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        assert drive_file.document_id == 42

    async def test_unsupported_file_marks_document_ready(self) -> None:
        from app.lib.rag import UnsupportedFileTypeError

        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(side_effect=UnsupportedFileTypeError("nope")),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.READY

    async def test_scanned_pdf_marks_document_failed(self) -> None:
        from app.lib.rag import ScannedPDFError

        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(side_effect=ScannedPDFError("scan.pdf")),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED

    async def test_new_file_full_pipeline_marks_document_ready(self) -> None:
        from app.lib.rag import IngestionResult

        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"x")),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(return_value=IngestionResult(new_chunks=3, reused_chunks=1)),
            ) as mock_ingest,
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        mock_ingest.assert_awaited_once()
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.READY

    async def test_none_id_returns_early(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        drive_file.id = None
        session = _make_async_session()
        with patch("app.core_plugins.googledrive.utils.update_document_status", new=AsyncMock()) as mock_update:
            await _process_single_file(drive_file, 1, "tok", session)
        mock_update.assert_not_awaited()

    async def test_duplicate_file_calls_copy_chunk_links(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(return_value=b"dup content"),
            ),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=99),
            ),
            patch("app.core_plugins.googledrive.utils.copy_chunk_links", new=AsyncMock()) as mock_copy,
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        mock_copy.assert_awaited_once_with(99, 10)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.READY

    async def test_drive_api_error_marks_document_failed(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(side_effect=GoogleDriveAPIError(500, "Error")),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED

    async def test_value_error_marks_document_failed(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(side_effect=ValueError("bad")),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED

    async def test_google_doc_filename_resolved(self) -> None:
        from app.lib.rag import IngestionResult

        drive_file = _make_drive_file(
            name="My Doc",
            mime_type="application/vnd.google-apps.document",
            document_id=10,
        )
        session = _make_async_session()
        with (
            patch("app.core_plugins.googledrive.utils.update_document_status", new=AsyncMock()),
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(return_value=b"content"),
            ),
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                return_value=None,
            ),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(return_value=IngestionResult(new_chunks=1, reused_chunks=0)),
            ) as mock_ingest,
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        assert mock_ingest.call_args.args[3] == "My Doc.pdf"

    async def test_size_guard_drive_reported_marks_document_failed(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        drive_file.size = 200 * 1024 * 1024  # 200 MB
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock()) as mock_dl,
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED
        assert "too large" in (last_call.args[3] or "")
        mock_dl.assert_not_awaited()

    async def test_size_guard_post_download_marks_document_failed(self) -> None:
        drive_file = _make_drive_file(document_id=10)
        drive_file.size = None
        session = _make_async_session()
        big_bytes = b"x" * (60 * 1024 * 1024)
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(return_value=big_bytes),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED
        assert "too large" in (last_call.args[3] or "")

    async def test_integrity_error_rollback_and_marks_document_failed(self) -> None:
        from sqlalchemy.exc import IntegrityError

        drive_file = _make_drive_file(document_id=10)
        session = _make_async_session()
        with (
            patch(
                "app.core_plugins.googledrive.utils.update_document_status",
                new=AsyncMock(),
            ) as mock_update,
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(side_effect=IntegrityError(None, None, Exception("dup"))),
            ),
        ):
            await _process_single_file(drive_file, 1, "tok", session)
        session.rollback.assert_awaited_once()
        from app.core.documents.enums import DocumentStatus

        last_call = mock_update.call_args_list[-1]
        assert last_call.args[2] == DocumentStatus.FAILED


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
        done_result = MagicMock()
        done_result.all.return_value = []
        mock_session.exec = AsyncMock(side_effect=[folder_result, files_result, done_result])
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await process_folder_rag(1, user_id=1, access_token="tok")

    @patch("app.core_plugins.googledrive.utils._process_single_file")
    @patch("app.core_plugins.googledrive.utils.session_scope")
    async def test_skips_ready_and_processing_files(self, mock_session_cls: MagicMock, mock_process: AsyncMock) -> None:
        ready_file = _make_drive_file(file_id=1, document_id=10)
        processing_file = _make_drive_file(file_id=3, document_id=20)
        pending_file = _make_drive_file(file_id=2, document_id=None)
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        list_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.first.return_value = folder
        files_result = MagicMock()
        files_result.all.return_value = [ready_file, processing_file, pending_file]
        done_result = MagicMock()
        done_result.all.return_value = [10, 20]
        list_session.exec = AsyncMock(side_effect=[folder_result, files_result, done_result])

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
        pending_file = _make_drive_file(file_id=1, document_id=None)
        folder = DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test")

        list_session = AsyncMock()
        folder_result = MagicMock()
        folder_result.first.return_value = folder
        files_result = MagicMock()
        files_result.all.return_value = [pending_file]
        done_result = MagicMock()
        done_result.all.return_value = []
        list_session.exec = AsyncMock(side_effect=[folder_result, files_result, done_result])

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

        await process_folder_rag(1, user_id=1, access_token="tok")
