from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.models.user import User

URL = "/api/v1/events/"

CLIENT_BODY = {
    "event_type": "test.client_event",
    "version": 1,
    "payload": {"value": "hello"},
}
SERVER_BODY = {
    "event_type": "assessment.submitted",
    "version": 1,
    "payload": {"learner_id": "u1", "competency_id": "c1", "score": 0.9, "passed": True},
}


async def test_emit_accepts_client_emittable_event(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    response = await client.post(URL, json=CLIENT_BODY)
    assert response.status_code == 202
    assert response.json() == {"accepted": True}

    count = (await analytics_session.execute(select(func.count()).select_from(raw_events))).scalar_one()
    assert count == 1
    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == "test.client_event"
    assert row["actor_id"] == str(current_user.id)


async def test_emit_server_only_event_returns_403(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    response = await client.post(URL, json=SERVER_BODY)
    assert response.status_code == 403

    count = (await analytics_session.execute(select(func.count()).select_from(raw_events))).scalar_one()
    assert count == 0


async def test_emit_ignores_client_supplied_occurred_at(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    far_past = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    body = {**CLIENT_BODY, "occurred_at": far_past}
    response = await client.post(URL, json=body)
    assert response.status_code == 202

    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    # occurred_at must be server-stamped (within the last minute), not the client value.
    # SQLite returns naive datetimes; treat as UTC for comparison.
    occurred_at = row["occurred_at"]
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    assert occurred_at > datetime.now(timezone.utc) - timedelta(minutes=1)


async def test_emit_requires_authentication(client: AsyncClient, analytics_session: AsyncSession) -> None:
    response = await client.post(URL, json=CLIENT_BODY)
    assert response.status_code == 403


async def test_emit_unknown_event_type_returns_422(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    body = {**CLIENT_BODY, "event_type": "does.not.exist"}
    response = await client.post(URL, json=body)
    assert response.status_code == 422


async def test_emit_invalid_payload_returns_422(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    body = {**CLIENT_BODY, "payload": {}}
    response = await client.post(URL, json=body)
    assert response.status_code == 422
