"""Tests for Google Drive per-file size guard before RAG ingestion."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.googledrive.models import DriveFile
from app.core_plugins.googledrive.utils import _process_single_file
from app.lib.documents import Document, DocumentStatus


@pytest.mark.asyncio
async def test_file_exceeding_size_limit_is_marked_failed(session: AsyncSession) -> None:
    """A downloaded file exceeding the configured size limit is marked failed."""
    drive_file = DriveFile(
        id=1,
        user_id=1,
        name="huge.pdf",
        drive_file_id="drive-id-123",
        mime_type="application/pdf",
        folder_id=1,
        size=None,
    )
    session.add(drive_file)
    await session.flush()
    await session.refresh(drive_file)
    drive_file_id = drive_file.id
    big_bytes = b"x" * (51 * 1024 * 1024)

    with (
        patch("app.core_plugins.googledrive.utils._download_file", new=AsyncMock(return_value=big_bytes)),
        patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.ingest_document") as mock_ingest,
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

    file_result = await session.exec(select(DriveFile).where(DriveFile.id == drive_file_id))
    refreshed_file = file_result.first()
    assert refreshed_file is not None
    assert refreshed_file.document_id is not None

    doc_result = await session.exec(select(Document).where(Document.id == refreshed_file.document_id))
    doc = doc_result.first()
    assert doc is not None
    assert doc.status == DocumentStatus.FAILED
    assert "too large" in (doc.error or "").lower()
    mock_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_pre_download_size_guard_skips_download(session: AsyncSession) -> None:
    """A Drive-reported size over the limit is rejected without downloading."""
    drive_file = DriveFile(
        id=3,
        user_id=1,
        name="massive.pdf",
        drive_file_id="drive-id-789",
        mime_type="application/pdf",
        folder_id=1,
        size=500 * 1024 * 1024,
    )
    session.add(drive_file)
    await session.flush()
    drive_file_id = drive_file.id

    with (
        patch("app.core_plugins.googledrive.utils._download_file") as mock_download,
        patch("app.core_plugins.googledrive.utils.get_googledrive_settings") as mock_settings,
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

    file_result = await session.exec(select(DriveFile).where(DriveFile.id == drive_file_id))
    refreshed_file = file_result.first()
    assert refreshed_file is not None
    assert refreshed_file.document_id is not None

    doc_result = await session.exec(select(Document).where(Document.id == refreshed_file.document_id))
    doc = doc_result.first()
    assert doc is not None
    assert doc.status == DocumentStatus.FAILED
    assert "too large" in (doc.error or "").lower()
    mock_download.assert_not_called()


@pytest.mark.asyncio
async def test_file_within_size_limit_proceeds_to_extraction(session: AsyncSession) -> None:
    """A file within the limit reaches RAG ingestion instead of size rejection."""
    drive_file = DriveFile(
        id=2,
        user_id=1,
        name="small.pdf",
        drive_file_id="drive-id-456",
        mime_type="application/pdf",
        folder_id=1,
    )
    session.add(drive_file)
    await session.flush()
    drive_file_id = drive_file.id

    small_bytes = b"x" * (1 * 1024 * 1024)

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
        patch("app.core_plugins.googledrive.utils._find_ready_duplicate_document_id", new=AsyncMock(return_value=None)),
    ):
        mock_settings.return_value.INGESTION_MAX_FILE_SIZE_MB = 50
        mock_settings.return_value.INGESTION_CONCURRENCY = 1
        await _process_single_file(drive_file, user_id=1, access_token="tok", session=session)

    file_result = await session.exec(select(DriveFile).where(DriveFile.id == drive_file_id))
    refreshed_file = file_result.first()
    assert refreshed_file is not None
    assert refreshed_file.document_id is not None

    doc_result = await session.exec(select(Document).where(Document.id == refreshed_file.document_id))
    doc = doc_result.first()
    assert doc is not None
    assert doc.status == DocumentStatus.FAILED
    assert "too large" not in (doc.error or "").lower()
