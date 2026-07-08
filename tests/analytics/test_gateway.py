import pytest
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.exceptions import UnknownEventTypeError
from sparkth.core.analytics.gateway import ingest_event
from sparkth.core.analytics.models import raw_events

GOOD_PAYLOAD = {"learner_id": "u1", "competency_id": "c1", "score": 0.9, "passed": True}


async def test_ingest_event_lands_one_row(analytics_session: AsyncSession) -> None:
    await ingest_event(
        analytics_session,
        "assessment.submitted",
        1,
        GOOD_PAYLOAD,
        actor_id="42",
    )
    count = (await analytics_session.execute(select(func.count()).select_from(raw_events))).scalar_one()
    assert count == 1

    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == "assessment.submitted"
    assert row["event_version"] == 1
    assert row["actor_id"] == "42"
    assert row["payload"] == GOOD_PAYLOAD
    assert row["occurred_at"] is not None


async def test_ingest_event_unknown_type_raises_and_writes_nothing(analytics_session: AsyncSession) -> None:
    with pytest.raises(UnknownEventTypeError):
        await ingest_event(
            analytics_session,
            "does.not.exist",
            1,
            GOOD_PAYLOAD,
        )
    count = (await analytics_session.execute(select(func.count()).select_from(raw_events))).scalar_one()
    assert count == 0


async def test_ingest_event_invalid_payload_raises(analytics_session: AsyncSession) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await ingest_event(
            analytics_session,
            "assessment.submitted",
            1,
            {"learner_id": "only"},
        )
