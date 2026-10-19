"""Tests for ``GET /api/v1/google-drive/analytics/documents``."""

from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.analytics import ingest_event
from sparkth.lib.models import User
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/google-drive/analytics/documents"


async def _seed(session: SQLAlchemyAsyncSession, outcome: str, seconds: int) -> None:
    await ingest_event(
        session,
        "google-drive.document_processed",
        1,
        {
            "document_id": 1,
            "outcome": outcome,
            "mime_type": "application/pdf",
            "size_bytes": 10,
            "chunk_count": 0,
            "seconds_to_final": seconds,
        },
        actor_id="1",
        occurred_at=datetime(2026, 3, 2, 12, tzinfo=timezone.utc),
    )


async def test_counts_and_sums_per_outcome(
    client: AsyncClient, current_user: User, session: AsyncSession, analytics_session: SQLAlchemyAsyncSession
) -> None:
    session.add(current_user)
    await session.flush()
    await grant_global_permission(session, 1, "analytics.read")
    await session.commit()
    for outcome, seconds in (("ingested", 30), ("ingested", 10), ("scanned_pdf", 4)):
        await _seed(analytics_session, outcome, seconds)

    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31", "bucket": "month"})

    assert response.status_code == 200
    assert response.json() == [
        {"bucket": "2026-03-01", "outcome": "ingested", "document_count": 2, "seconds_total": 40},
        {"bucket": "2026-03-01", "outcome": "scanned_pdf", "document_count": 1, "seconds_total": 4},
    ]


async def test_requires_analytics_read(client: AsyncClient, current_user: User) -> None:
    response = await client.get(URL, params={"from": "2026-03-01", "to": "2026-03-31"})

    assert response.status_code == 403
