"""Audit rows are append-only at the database level, not just by convention:
UPDATE, DELETE, and whole-table deletion are rejected by triggers that ship
with the table itself."""

import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import AuditOutcome, LoginAuditEvent
from sparkth.lib.testing import AuditEventsFetcher


@pytest.fixture
async def recorded(session: AsyncSession) -> AuditEvent:
    row = await record_event(session, LoginAuditEvent(outcome=AuditOutcome.SUCCESS))
    await session.commit()
    return row


async def test_update_is_rejected(session: AsyncSession, recorded: AuditEvent) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(update(AuditEvent).where(col(AuditEvent.id) == recorded.id).values(outcome="denied"))


async def test_delete_is_rejected(session: AsyncSession, recorded: AuditEvent) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(delete(AuditEvent).where(col(AuditEvent.id) == recorded.id))


async def test_whole_table_delete_is_rejected(session: AsyncSession, recorded: AuditEvent) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(text("DELETE FROM audit_events"))


async def test_inserts_still_work_and_rows_survive(
    session: AsyncSession, recorded: AuditEvent, audit_events: AuditEventsFetcher
) -> None:
    await session.rollback()
    await record_event(session, LoginAuditEvent(outcome=AuditOutcome.FAILURE))
    await session.commit()

    assert [event.outcome for event in await audit_events()] == ["success", "failure"]
