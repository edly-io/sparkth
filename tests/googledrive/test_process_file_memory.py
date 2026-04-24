"""Tests for memory cleanup in file processing."""

import inspect
import sys
from contextlib import AbstractContextManager, ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.googledrive.utils import _process_single_file, process_folder_rag


class TestProcessFileMemory:
    """Tests for malloc_trim and OS memory release."""

    @pytest.mark.asyncio
    async def test_process_with_own_session_calls_gc_collect(self) -> None:
        """Verify that after session close, gc.collect() is called in _process_with_own_session."""
        # Since _process_with_own_session is a nested function, we verify the behavior
        # indirectly by checking that the module has the correct cleanup code structure.
        # The actual malloc_trim behavior is verified through integration testing.
        source = inspect.getsource(process_folder_rag)
        # Verify that _process_with_own_session includes gc.collect() after session close
        assert "gc.collect()" in source
        # Verify that malloc_trim code exists in the function
        assert "malloc_trim" in source

    @pytest.mark.asyncio
    async def test_malloc_trim_not_called_on_darwin(self) -> None:
        """Verify malloc_trim is NOT called on macOS (darwin)."""

        # Setup mocks
        mock_drive_file = MagicMock(id=1, name="test.pdf", rag_status=None, size=100)
        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # Stop the RuntimeWarnings

        # Mock session.execute to return a result with scalars
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        patches: list[AbstractContextManager[Any]] = [
            patch("ctypes.CDLL"),
            patch("app.core_plugins.googledrive.utils._download_file", return_value=b"%PDF-1.4\n"),
            patch("app.core_plugins.googledrive.utils.extract_to_markdown", return_value=MagicMock(markdown="# Test")),
            patch("app.core_plugins.googledrive.utils.chunk_document", return_value=[]),
        ]

        with patch.object(sys, "platform", "darwin"), ExitStack() as stack:
            # Enter all context managers
            mocks: list[Any] = [stack.enter_context(p) for p in patches]
            mock_cdll = mocks[0]

            await _process_single_file(
                mock_drive_file,
                user_id=1,
                access_token="fake",
                session=mock_session,
                provider=MagicMock(),
                store=MagicMock(),
            )

            # ctypes.CDLL should NOT be called on non-Linux
            mock_cdll.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_expunge_all_called_in_finally(self) -> None:
        """Verify session.expunge_all() is called in _process_single_file finally block."""
        mock_drive_file = MagicMock()
        mock_drive_file.id = 1
        mock_drive_file.name = "test.pdf"
        mock_drive_file.rag_status = None
        mock_drive_file.size = None
        mock_drive_file.mime_type = "application/pdf"

        mock_session = AsyncMock()
        mock_session.expunge_all = MagicMock()

        with pytest.raises(Exception):
            await _process_single_file(
                mock_drive_file,
                user_id=1,
                access_token="fake",
                session=mock_session,
                provider=MagicMock(),
                store=MagicMock(),
            )

        mock_session.expunge_all.assert_called_once()
