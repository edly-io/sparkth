"""Tests for memory cleanup in file processing."""

import inspect
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.googledrive.utils import _process_single_file, _process_with_semaphore


class TestProcessFileMemory:
    """Tests for malloc_trim and OS memory release."""

    @pytest.mark.asyncio
    async def test_process_with_semaphore_calls_gc_collect(self) -> None:
        """Verify that gc.collect() and malloc_trim logic live in _process_with_semaphore."""
        source = inspect.getsource(_process_with_semaphore)
        assert "gc.collect()" in source
        assert "malloc_trim" in source

    @pytest.mark.asyncio
    async def test_malloc_trim_not_called_on_darwin(self) -> None:
        """Verify malloc_trim is NOT called on macOS (darwin)."""
        mock_drive_file = MagicMock(id=1, name="test.pdf", size=None, document_id=None, mime_type="application/pdf")
        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        with (
            patch("ctypes.CDLL") as mock_cdll,
            patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=b"%PDF-1.4\n")),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
            patch(
                "app.core_plugins.googledrive.utils._find_ready_duplicate_document_id",
                new=AsyncMock(return_value=None),
            ),
            patch("app.core_plugins.googledrive.utils.create_document", new=AsyncMock(return_value=MagicMock(id=1))),
            patch(
                "app.core_plugins.googledrive.utils.ingest_document",
                new=AsyncMock(return_value=MagicMock(new_chunks=0, reused_chunks=0)),
            ),
            patch("app.core_plugins.googledrive.utils.update_document_status", new=AsyncMock()),
            patch.object(sys, "platform", "darwin"),
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50

            await _process_single_file(
                mock_drive_file,
                user_id=1,
                access_token="fake",
                session=mock_session,
            )

        # ctypes.CDLL should NOT be called on non-Linux (darwin)
        mock_cdll.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_expunge_all_called_in_finally(self) -> None:
        """Verify session.expunge_all() is called in _process_single_file finally block."""
        mock_drive_file = MagicMock()
        mock_drive_file.id = 1
        mock_drive_file.name = "test.pdf"
        mock_drive_file.size = None
        mock_drive_file.mime_type = "application/pdf"

        mock_session = AsyncMock()
        mock_session.expunge_all = MagicMock()

        # Trigger the generic Exception branch by raising from _download_file
        with (
            patch(
                "app.core_plugins.googledrive.utils._download_file",
                new=AsyncMock(side_effect=Exception("unexpected boom")),
            ),
            patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
        ):
            mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50

            with pytest.raises(Exception):
                await _process_single_file(
                    mock_drive_file,
                    user_id=1,
                    access_token="fake",
                    session=mock_session,
                )

        mock_session.expunge_all.assert_called_once()
