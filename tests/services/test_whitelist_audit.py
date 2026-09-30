"""Every change to the registration allowlist leaves an audit row, atomically
with the change: a failed add or remove records nothing."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.whitelist import WhitelistedEmail
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.services.whitelist import (
    InvalidWhitelistValue,
    WhitelistEntryAlreadyExists,
    WhitelistEntryNotFound,
    WhitelistService,
)


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_add_entry_records_entry_added(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    raw = f"  {_uniq('User')}@Example.com "
    entry = await WhitelistService.add_entry(session, value=raw, added_by_id=1)

    (event,) = await audit_events()
    assert (event.category, event.action) == ("whitelist", "entry_added")
    assert event.outcome == "success"
    assert event.target_type == "whitelist_entry"
    assert event.target_id == str(entry.id)
    assert event.old_values is None
    assert event.new_values == {"value": raw.strip().lower(), "entry_type": "email"}


async def test_add_domain_entry_records_its_type(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    domain = f"@{_uniq('org')}.com"
    await WhitelistService.add_entry(session, value=domain, added_by_id=1)

    (event,) = await audit_events()
    assert event.new_values == {"value": domain, "entry_type": "domain"}


async def test_duplicate_add_records_nothing_more(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    email = f"{_uniq('user')}@example.com"
    await WhitelistService.add_entry(session, value=email, added_by_id=1)

    with pytest.raises(WhitelistEntryAlreadyExists):
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

    (event,) = await audit_events()
    assert event.action == "entry_added"


async def test_invalid_add_records_nothing(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    with pytest.raises(InvalidWhitelistValue):
        await WhitelistService.add_entry(session, value="not-an-email", added_by_id=1)

    assert await audit_events() == []


async def test_failed_add_commit_rolls_the_record_back(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_commit() -> None:
        raise IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))

    monkeypatch.setattr(session, "commit", failing_commit)
    email = f"{_uniq('fk')}@example.com"

    with pytest.raises(IntegrityError):
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

    assert (await session.exec(select(WhitelistedEmail))).all() == []
    assert await audit_events() == []


async def test_add_is_fail_closed_when_audit_write_fails(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_record(*_args: object, **_kwargs: object) -> None:
        raise SQLAlchemyError("audit store down")

    monkeypatch.setattr("sparkth.services.whitelist.service.record_event", broken_record)

    with pytest.raises(SQLAlchemyError):
        await WhitelistService.add_entry(session, value=f"{_uniq('user')}@example.com", added_by_id=1)
    await session.rollback()

    assert (await session.exec(select(WhitelistedEmail))).all() == []


async def test_remove_entry_records_entry_removed(session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
    domain = f"@{_uniq('org')}.com"
    entry = await WhitelistService.add_entry(session, value=domain, added_by_id=1)
    assert entry.id is not None

    await WhitelistService.remove_entry(session, entry_id=entry.id)

    _, event = await audit_events()
    assert (event.category, event.action) == ("whitelist", "entry_removed")
    assert event.outcome == "success"
    assert event.target_type == "whitelist_entry"
    assert event.target_id == str(entry.id)
    assert event.old_values == {"value": domain, "entry_type": "domain"}
    assert event.new_values is None


async def test_removing_a_missing_entry_records_nothing(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    with pytest.raises(WhitelistEntryNotFound):
        await WhitelistService.remove_entry(session, entry_id=999999)

    assert await audit_events() == []


async def test_failed_remove_commit_rolls_the_record_back(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = await WhitelistService.add_entry(session, value=f"{_uniq('user')}@example.com", added_by_id=1)
    assert entry.id is not None
    entry_id = entry.id

    async def failing_commit() -> None:
        raise SQLAlchemyError("connection lost")

    monkeypatch.setattr(session, "commit", failing_commit)
    with pytest.raises(SQLAlchemyError):
        await WhitelistService.remove_entry(session, entry_id=entry_id)
    await session.rollback()

    assert await session.get(WhitelistedEmail, entry_id) is not None
    (event,) = await audit_events()
    assert event.action == "entry_added"
