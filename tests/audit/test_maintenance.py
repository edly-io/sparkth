"""Retention purge and GDPR erasure are the only two sanctioned writes past the
append-only guard: the purge deletes whole rows per category once they are older
than the configured retention, erasure blanks the personal-data columns that sit
outside the sealed canonical bytes for one actor. Both leave their own audit event
behind and re-arm the guard when they are done.
Authored with LLM (Claude) assistance."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import DBAPIError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.lib.audit import erase_actor, purge_expired_events, record_event
from sparkth.lib.audit.context import AuditRequestContext, UserActor, audit_context
from sparkth.lib.audit.events import AuditOutcome, LoginAuditEvent, ToolInvokedAuditEvent
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import AuditEventsFetcher

NOW = datetime.now(timezone.utc)
ALICE = UserActor(id="1", label="alice")
BOB = UserActor(id="2", label="bob")


async def _login(session: AsyncSession, actor: UserActor, *, days_ago: int) -> None:
    occurred_at = NOW - timedelta(days=days_ago)
    await record_event(session, LoginAuditEvent(outcome=AuditOutcome.SUCCESS, actor=actor, occurred_at=occurred_at))


async def _tool(session: AsyncSession, actor: UserActor, *, days_ago: int) -> None:
    occurred_at = NOW - timedelta(days=days_ago)
    await record_event(
        session, ToolInvokedAuditEvent(outcome=AuditOutcome.SUCCESS, actor=actor, occurred_at=occurred_at)
    )


@pytest.fixture
def retention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "AUDIT_RETENTION_DAYS", 30)
    monkeypatch.setattr(get_settings(), "AUDIT_RETENTION_OVERRIDES", {"tool": 10})


async def test_purge_deletes_per_category_and_records_what_it_removed(
    session: AsyncSession, audit_events: AuditEventsFetcher, retention: None
) -> None:
    await _login(session, ALICE, days_ago=31)  # past the 30-day default
    await _login(session, ALICE, days_ago=29)  # kept
    await _tool(session, ALICE, days_ago=11)  # past the 10-day tool override
    await _tool(session, ALICE, days_ago=9)  # kept
    await session.commit()

    deleted = await purge_expired_events()

    assert deleted == {"tool": 1, "*": 1}
    rows = await audit_events()
    kept = [(r.category, r.action) for r in rows if r.category != "audit"]
    assert kept == [("auth", "login"), ("tool", "invoked")]
    purged = [r for r in rows if r.category == "audit"]
    assert [(r.action, r.actor_type, r.old_values) for r in purged] == [
        ("retention_purged", "system", {"category": "tool", "retention_days": 10, "deleted_rows": 1}),
        ("retention_purged", "system", {"category": "*", "retention_days": 30, "deleted_rows": 1}),
    ]


async def test_purge_with_nothing_expired_records_nothing(
    session: AsyncSession, audit_events: AuditEventsFetcher, retention: None
) -> None:
    await _login(session, ALICE, days_ago=1)
    await session.commit()

    assert await purge_expired_events() == {}
    assert len(await audit_events()) == 1


async def test_zero_retention_keeps_a_category_forever(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "AUDIT_RETENTION_DAYS", 0)
    monkeypatch.setattr(get_settings(), "AUDIT_RETENTION_OVERRIDES", {"tool": 0})
    await _login(session, ALICE, days_ago=5000)
    await _tool(session, ALICE, days_ago=5000)
    await session.commit()

    assert await purge_expired_events() == {}
    assert len(await audit_events()) == 2


async def test_guard_is_rearmed_after_purge(session: AsyncSession, retention: None) -> None:
    await _login(session, ALICE, days_ago=31)
    await session.commit()
    await purge_expired_events()

    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(delete(AuditEvent))


async def test_erase_actor_blanks_only_that_actors_origin_columns(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    with audit_context(AuditRequestContext(request_id="r1", request_ip="9.9.9.9", user_agent="ua")):
        await _login(session, ALICE, days_ago=1)
        await _login(session, BOB, days_ago=1)
    await session.commit()

    assert await erase_actor(1) == 1

    alice, bob, erased = await audit_events()
    assert (alice.actor_id, alice.actor_label, alice.request_ip, alice.user_agent) == ("1", None, None, None)
    assert (alice.category, alice.action, alice.outcome, alice.request_id) == ("auth", "login", "success", "r1")
    assert (bob.actor_label, bob.request_ip, bob.user_agent) == ("bob", "9.9.9.9", "ua")
    assert (erased.category, erased.action, erased.actor_type) == ("audit", "actor_erased", "system")
    assert (erased.target_type, erased.target_id, erased.old_values) == ("user", "1", {"rows": 1})
    assert b"alice" not in alice.canonical_bytes


async def test_guard_is_rearmed_after_erasure(session: AsyncSession) -> None:
    await _login(session, ALICE, days_ago=1)
    await session.commit()
    await erase_actor(1)

    with pytest.raises(DBAPIError, match="append-only"):
        await session.execute(delete(AuditEvent))
