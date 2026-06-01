"""Tests for per-file size guard in RAG pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.googledrive.utils import DriveRagPipeline
from app.rag.types import RagStatus


@pytest.mark.asyncio
async def test_file_exceeding_size_limit_is_marked_failed(session: AsyncSession) -> None:
    """A file whose downloaded bytes exceed RAG_MAX_FILE_SIZE_MB is marked FAILED (post-download guard)."""
    from app.models.drive import DriveFile

    drive_file = DriveFile(
        id=1,
        user_id=1,
        name="huge.pdf",
        drive_file_id="drive-id-123",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
        size=None,
    )
    session.add(drive_file)
    await session.flush()
    await session.refresh(drive_file)
    drive_file_id = drive_file.id
    big_bytes = b"x" * (51 * 1024 * 1024)
    mock_store = MagicMock()
    with (
        patch(
            "app.core_plugins.googledrive.utils.DriveRagPipeline._download_file", new=AsyncMock(return_value=big_bytes)
        ),
        patch("app.core_plugins.googledrive.utils.get_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.extract_to_markdown") as mock_extract,
    ):
        mock_settings.return_value.RAG_MAX_FILE_SIZE_MB = 50
        await DriveRagPipeline()._process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, store=mock_store
        )
    from app.models.drive import DriveFile

    result = await session.exec(select(DriveFile).where(DriveFile.id == drive_file_id))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" in (refreshed_file.rag_error or "").lower()
    mock_extract.assert_not_called()


@pytest.mark.asyncio
async def test_pre_download_size_guard_skips_download(session: AsyncSession) -> None:
    """When DriveFile.size exceeds the limit, file is rejected without downloading."""
    from app.models.drive import DriveFile

    drive_file = DriveFile(
        id=3,
        user_id=1,
        name="massive.pdf",
        drive_file_id="drive-id-789",
        mime_type="application/pdf",
        folder_id=1,
        rag_status=RagStatus.QUEUED,
        size=500 * 1024 * 1024,
    )
    session.add(drive_file)
    await session.flush()

    mock_store = MagicMock()

    with (
        patch("app.core_plugins.googledrive.utils.DriveRagPipeline._download_file") as mock_download,
        patch("app.core_plugins.googledrive.utils.get_settings") as mock_settings,
    ):
        mock_settings.return_value.RAG_MAX_FILE_SIZE_MB = 50
        await DriveRagPipeline()._process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, store=mock_store
        )

    result = await session.exec(select(DriveFile).where(DriveFile.id == 3))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" in (refreshed_file.rag_error or "").lower()
    mock_download.assert_not_called()


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

    small_bytes = b"x" * (1 * 1024 * 1024)

    mock_store = MagicMock()

    with (
        patch(
            "app.core_plugins.googledrive.utils.DriveRagPipeline._download_file",
            new=AsyncMock(return_value=small_bytes),
        ),
        patch("app.core_plugins.googledrive.utils.get_settings") as mock_settings,
        patch("app.core_plugins.googledrive.utils.extract_to_markdown", side_effect=RuntimeError("stop here")),
    ):
        mock_settings.return_value.RAG_MAX_FILE_SIZE_MB = 50
        mock_settings.return_value.RAG_CONCURRENCY = 1
        await DriveRagPipeline()._process_single_file(
            drive_file, user_id=1, access_token="tok", session=session, store=mock_store
        )

    result = await session.exec(select(DriveFile).where(DriveFile.id == 2))
    refreshed_file = result.first()
    assert refreshed_file is not None
    assert refreshed_file.rag_status == RagStatus.FAILED
    assert "too large" not in (refreshed_file.rag_error or "").lower()
