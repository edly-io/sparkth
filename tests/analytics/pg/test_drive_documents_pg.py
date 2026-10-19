"""TimescaleDB-backed tests for the Drive documents read (the ``pg``-marked lane)."""

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import Bucket, ingest_event
from sparkth.plugins.googledrive.analytics.reads import get_drive_documents

pytestmark = pytest.mark.pg


def _at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)


def _payload(outcome: str, seconds: int) -> dict[str, object]:
    return {
        "document_id": 1,
        "outcome": outcome,
        "mime_type": "application/pdf",
        "size_bytes": 10,
        "chunk_count": 0,
        "seconds_to_final": seconds,
    }


async def test_pg_drive_documents_cagg_exists(pg_analytics_session: AsyncSession) -> None:
    rows = await pg_analytics_session.execute(
        text(
            "SELECT view_name FROM timescaledb_information.continuous_aggregates"
            " WHERE view_name = 'googledrive_documents_daily'"
        )
    )
    assert rows.scalars().all() == ["googledrive_documents_daily"]


@pytest.mark.parametrize("bucket", list(Bucket))
async def test_pg_drive_documents_matches_sqlite(
    pg_analytics_session: AsyncSession,
    pg_refresh: Callable[[], Awaitable[None]],
    analytics_session: AsyncSession,
    bucket: Bucket,
) -> None:
    seed = [
        (_at("2025-11-30", 23), _payload("ingested", 5)),
        (_at("2025-12-01", 0), _payload("ingested", 7)),
        (_at("2025-12-01"), _payload("scanned_pdf", 2)),
        (_at("2025-12-29"), _payload("duplicate", 1)),
        (_at("2026-01-31", 23), _payload("drive_error", 9)),
        (_at("2026-02-01", 0), _payload("ingested", 3)),
    ]
    for session in (pg_analytics_session, analytics_session):
        for occurred_at, payload in seed:
            await ingest_event(
                session, "google-drive.document_processed", 1, payload, actor_id="1", occurred_at=occurred_at
            )
    await pg_refresh()

    pg_result = await get_drive_documents(pg_analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)
    sqlite_result = await get_drive_documents(analytics_session, date(2025, 12, 1), date(2026, 1, 31), bucket)

    assert pg_result == sqlite_result
    assert sum(p.seconds_total for p in pg_result) == 7 + 2 + 1 + 9
