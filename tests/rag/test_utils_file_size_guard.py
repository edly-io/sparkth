"""Tests for per-file size guard in RAG pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.googledrive.utils import _process_single_file
from app.rag.types import RagStatus


@pytest.mark.asyncio
async def test_file_exceeding_size_limit_is_marked_failed(session: AsyncSession) -> None:
    """A file whose bytes exceed RAG_MAX_FILE_SIZE_MB is marked FAILED, not extracted."""
    from app.models.drive import DriveFile

    drive_file = DriveFile(
        id=1,
        user_id=1,
        name="huge.pdf",
        drive_file_id="drive-id-123",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
    )
    session.add(drive_file)
    await session.flush()

    # 51 MB of bytes — exceeds default limit of 50 MB
    big_bytes = b"x" * (51 * 1024 * 1024)

    mock_provider = MagicMock()
    mock_store = MagicMock()

    with (
        patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=big_bytes)),
        patch("app.core_plugins.googledrive.utils.get_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.extract_to_markdown") as mock_extract,
    ):
        mock_settings.return_value.RAG_MAX_FILE_SIZE_MB = 50
        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=mock_provider, store=mock_store
        )

    await session.refresh(drive_file)
    assert drive_file.rag_status == RagStatus.FAILED
    assert "too large" in (drive_file.rag_error or "").lower()
    # Extraction must NOT have been called
    mock_extract.assert_not_called()


@pytest.mark.asyncio
async def test_file_within_size_limit_proceeds_to_extraction(session: AsyncSession) -> None:
    """A file within size limit is NOT rejected by size guard."""
    from app.models.drive import DriveFile

    drive_file = DriveFile(
        id=2,
        user_id=1,
        name="small.pdf",
        drive_file_id="drive-id-456",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
    )
    session.add(drive_file)
    await session.flush()

    small_bytes = b"x" * (1 * 1024 * 1024)  # 1 MB, well within limit

    mock_provider = MagicMock()
    mock_store = MagicMock()

    # We only care that extraction IS reached, not that it completes
    with (
        patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=small_bytes)),
        patch("app.core_plugins.googledrive.utils.get_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.extract_to_markdown", side_effect=RuntimeError("stop here")),
    ):
        mock_settings.return_value.RAG_MAX_FILE_SIZE_MB = 50
        mock_settings.return_value.RAG_CONCURRENCY = 1
        # RuntimeError is caught by _process_single_file's except clause
        await _process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, provider=mock_provider, store=mock_store
        )

    # The file should NOT be QUEUED (guard did not fire); it reached extraction and then FAILED
    await session.refresh(drive_file)
    assert drive_file.rag_status == RagStatus.FAILED
    assert "too large" not in (drive_file.rag_error or "").lower()
