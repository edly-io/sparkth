"""Tests for per-file size guard in RAG pipeline."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.googledrive.utils import _process_single_file
from app.lib.rag import RagStatus
from app.models.drive import DriveFile


@pytest.mark.asyncio
async def test_file_exceeding_size_limit_is_marked_failed(session: AsyncSession) -> None:
    """A file whose downloaded bytes exceed INGESTION_MAX_FILE_SIZE_MB is marked FAILED (post-download guard)."""
    drive_file = DriveFile(
        id=1,
        user_id=1,
        name="huge.pdf",
        drive_file_id="drive-id-123",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
        size=None,  # No Drive-reported size — forces post-download check
    )
    session.add(drive_file)
    await session.flush()
    await session.refresh(drive_file)
    # Store the ID before calling _process_single_file which might expunge the object
    drive_file_id = drive_file.id
    # 51 MB of bytes — exceeds default limit of 50 MB
    big_bytes = b"x" * (51 * 1024 * 1024)
    with (
        patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=big_bytes)),
        patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.ingest_document") as mock_ingest,
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)
    # Re-fetch the drive_file from the database since expunge_all() detaches it
    result = await session.exec(select(DriveFile).where(DriveFile.id == drive_file_id))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" in (refreshed_file.rag_error or "").lower()
    # ingest_document must NOT have been called
    mock_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_download_size_guard_skips_download(session: AsyncSession) -> None:
    """When DriveFile.size exceeds the limit, file is rejected without downloading."""
    drive_file = DriveFile(
        id=3,
        user_id=1,
        name="massive.pdf",
        drive_file_id="drive-id-789",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
        size=500 * 1024 * 1024,  # 500 MB — far exceeds 50 MB limit
    )
    session.add(drive_file)
    await session.flush()

    with (
        patch("app.core_plugins.googledrive.utils._download_file") as mock_download,
        patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

    # Re-fetch the drive_file from the database since expunge_all() detaches it
    result = await session.exec(select(DriveFile).where(DriveFile.id == 3))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" in (refreshed_file.rag_error or "").lower()
    # _download_file must NOT have been called — file was rejected from metadata alone
    mock_download.assert_not_called()


@pytest.mark.asyncio
async def test_file_within_size_limit_proceeds_to_extraction(session: AsyncSession) -> None:
    """A file within size limit is NOT rejected by size guard."""
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

    # We only care that ingest_document IS reached (size guard did not block it)
    with (
        patch(
            "app.core_plugins.googledrive.utils._download_file",
            new=AsyncMock(return_value=small_bytes),
        ),
        patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
        patch(
            "app.core_plugins.googledrive.utils.ingest_document",
            new=AsyncMock(side_effect=RuntimeError("stop here")),
        ),
        patch("app.core_plugins.googledrive.utils._find_duplicate_file", new=AsyncMock(return_value=None)),
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        mock_settings.return_value.INGESTION_CONCURRENCY = 1
        # RuntimeError is caught by _process_single_file's except clause
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

    # Re-fetch the drive_file from the database since expunge_all() detaches it
    result = await session.exec(select(DriveFile).where(DriveFile.id == 2))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" not in (refreshed_file.rag_error or "").lower()
