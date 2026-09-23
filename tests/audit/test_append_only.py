"""Audit rows are append-only at the database level, not just by convention:
UPDATE, DELETE, and whole-table deletion are rejected by triggers that ship
with the table itself."""

import pytest
from sqlalchemy import Connection, create_engine, delete, text, update
from sqlalchemy.exc import DBAPIError
from sqlmodel import SQLModel, col
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent, install_append_only_triggers
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


def _trigger_names(connection: Connection) -> set[str]:
    rows = connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).all()
    return {row[0] for row in rows}


def test_installer_adds_missing_triggers_and_is_idempotent() -> None:
    """A database whose audit table predates the triggers (``create_all`` skips an
    existing table, so ``after_create`` never fires for it) gets them from the installer,
    and running the installer again is a no-op rather than an error."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        SQLModel.metadata.tables[AuditEvent.__tablename__].create(connection)
        for name in _trigger_names(connection):
            connection.execute(text(f"DROP TRIGGER {name}"))
        assert _trigger_names(connection) == set()

        install_append_only_triggers(connection)
        installed = _trigger_names(connection)
        assert installed == {"audit_events_no_update", "audit_events_no_delete"}

        install_append_only_triggers(connection)
        assert _trigger_names(connection) == installed
