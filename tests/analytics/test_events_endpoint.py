from httpx import AsyncClient
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.analytics.models import raw_events
from app.models.user import User

URL = "/api/v1/events/"
GOOD_BODY = {
    "event_type": "assessment.submitted",
    "version": 1,
    "payload": {"learner_id": "u1", "competency_id": "c1", "score": 0.9, "passed": True},
}


async def test_emit_accepts_valid_event(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    response = await client.post(URL, json=GOOD_BODY)
    assert response.status_code == 202
    assert response.json() == {"accepted": True}

    count = (await analytics_session.execute(select(func.count()).select_from(raw_events))).scalar_one()
    assert count == 1
    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == "assessment.submitted"
    assert row["actor_id"] == str(current_user.id)


async def test_emit_requires_authentication(client: AsyncClient, analytics_session: AsyncSession) -> None:
    # No Authorization header and no auth override: HTTPBearer rejects with 403.
    response = await client.post(URL, json=GOOD_BODY)
    assert response.status_code == 403


async def test_emit_unknown_event_type_returns_422(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    body = {**GOOD_BODY, "event_type": "does.not.exist"}
    response = await client.post(URL, json=body)
    assert response.status_code == 422


async def test_emit_invalid_payload_returns_422(
    client: AsyncClient, current_user: User, analytics_session: AsyncSession
) -> None:
    body = {**GOOD_BODY, "payload": {"learner_id": "only"}}
    response = await client.post(URL, json=body)
    assert response.status_code == 422
