"""Analytics producer tests: a sync run writes one ``google-drive.document_processed`` per document.

Drives the real ``process_folder_rag`` against the test databases and asserts on rows that
landed in ``raw_events``; only the Drive download and the RAG extraction are stubbed.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.rag import ScannedPDFError, UnsupportedFileTypeError
from sparkth.plugins.googledrive.exceptions import GoogleDriveAPIError
from sparkth.plugins.googledrive.models import DriveFile, DriveFolder
from sparkth.plugins.googledrive.utils import process_folder_rag

EVENT = "google-drive.document_processed"
PDF = b"%PDF-1.4\n"


async def _seed(session: AsyncSession, *, size: int | None = None, created_at: datetime | None = None) -> None:
    session.add(DriveFolder(id=1, user_id=1, drive_folder_id="abc", drive_folder_name="Test"))
    document = Document(id=10, user_id=1, name="doc.pdf", status=DocumentStatus.FAILED)
    if created_at is not None:
        document.created_at = created_at
    session.add(document)
    session.add(
        DriveFile(
            id=1,
            folder_id=1,
            user_id=1,
            drive_file_id="drive_1",
            name="doc.pdf",
            mime_type="application/pdf",
            size=size,
            document_id=10,
        )
    )
    await session.commit()


async def _rows(analytics_session: SQLAlchemyAsyncSession) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(sa_select(raw_events))).mappings().all()
    return [dict(r) for r in rows if r["event_type"] == EVENT]


async def _run(download: AsyncMock, ingest: AsyncMock | None = None) -> None:
    ingest = ingest or AsyncMock(return_value=MagicMock(new_chunks=3, reused_chunks=2))
    with (
        patch("sparkth.plugins.googledrive.utils._download_file", new=download),
        patch("sparkth.plugins.googledrive.utils.ingest_document", new=ingest),
    ):
        await process_folder_rag(1, user_id=1, access_token="tok")


async def test_ingested_document_records_one_event(
    session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _seed(session)

    await _run(AsyncMock(return_value=PDF))

    [row] = await _rows(analytics_session)
    assert row["actor_id"] == "1"
    payload = row["payload"]
    assert payload["document_id"] == 10
    assert payload["outcome"] == "ingested"
    assert payload["mime_type"] == "application/pdf"
    assert payload["size_bytes"] == len(PDF)
    assert payload["chunk_count"] == 5
    assert payload["seconds_to_final"] >= 0


async def test_duplicate_document_records_duplicate(
    session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _seed(session)
    with (
        patch(
            "sparkth.plugins.googledrive.utils._find_ready_duplicate_document_id",
            new=AsyncMock(return_value=99),
        ),
        patch("sparkth.plugins.googledrive.utils.copy_document_chunk_links", new=AsyncMock()),
    ):
        await _run(AsyncMock(return_value=PDF))

    [row] = await _rows(analytics_session)
    assert row["payload"]["outcome"] == "duplicate"
    assert row["payload"]["chunk_count"] == 0


async def test_oversized_document_records_too_large_without_downloading(
    session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    await _seed(session, size=51 * 1024 * 1024)  # the conftest limit is 50 MB
    download = AsyncMock(return_value=PDF)

    await _run(download)

    download.assert_not_awaited()
    [row] = await _rows(analytics_session)
    assert row["payload"]["outcome"] == "too_large"
    assert row["payload"]["size_bytes"] == 51 * 1024 * 1024


@pytest.mark.parametrize(
    ("download", "ingest_error", "outcome"),
    [
        (AsyncMock(return_value=PDF), UnsupportedFileTypeError("nope"), "unsupported_type"),
        (AsyncMock(return_value=PDF), ScannedPDFError("scan.pdf"), "scanned_pdf"),
        (AsyncMock(side_effect=GoogleDriveAPIError(500, "boom")), None, "drive_error"),
        (AsyncMock(side_effect=httpx.ConnectError("down")), None, "drive_error"),
        (AsyncMock(return_value=PDF), ValueError("bad"), "failed"),
        (AsyncMock(return_value=PDF), KeyError("unexpected"), "failed"),
    ],
    ids=["unsupported", "scanned", "drive-api", "drive-unreachable", "processing", "unexpected"],
)
async def test_failure_records_its_outcome(
    session: AsyncSession,
    analytics_session: SQLAlchemyAsyncSession,
    download: AsyncMock,
    ingest_error: Exception | None,
    outcome: str,
) -> None:
    await _seed(session)

    await _run(download, AsyncMock(side_effect=ingest_error) if ingest_error else None)

    [row] = await _rows(analytics_session)
    assert row["payload"]["outcome"] == outcome
    assert row["payload"]["chunk_count"] == 0


async def test_retry_times_from_the_sync_start(
    session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    """A failed document retried days later is timed from this sync, not from its creation."""
    await _seed(session, created_at=datetime.now(timezone.utc) - timedelta(days=3))

    await _run(AsyncMock(return_value=PDF))

    [row] = await _rows(analytics_session)
    assert row["payload"]["seconds_to_final"] < 60


async def test_emit_failure_leaves_document_status_final(session: AsyncSession) -> None:
    """The emit runs after the final status is committed, so a failed write can't undo it."""
    await _seed(session)
    with patch(
        "sparkth.plugins.googledrive.utils.emit_event",
        new=AsyncMock(side_effect=RuntimeError("analytics down")),
    ):
        await _run(AsyncMock(return_value=PDF))  # gather(return_exceptions=True) logs it

    session.expire_all()
    document = (await session.exec(select(Document).where(col(Document.id) == 10))).first()
    assert document is not None
    assert document.status == DocumentStatus.READY
