"""record_event is the single write path into audit_events. It joins the
caller's session (mutations and their audit records commit or roll back
together), enriches from the request context, redacts secrets, and stores the
canonical bytes the tamper-evidence sealer will later hash."""

from datetime import datetime, timezone

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit.canonical import canonicalize
from app.core.audit.redaction import REDACTED
from app.lib.audit import (
    AnonymousActor,
    AuditContext,
    AuditOutcome,
    AuditSource,
    UnknownAuditEventTypeError,
    UserActor,
    audit_context,
    record_event,
    record_event_now,
)
from app.models.audit import AuditEvent

ACTOR = UserActor(id="1", label="alice")


async def test_record_event_persists_with_caller_session(session: AsyncSession) -> None:
    await record_event(session, "auth.login", outcome=AuditOutcome.SUCCESS, actor=ACTOR)
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.category == "auth"
    assert event.action == "login"
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == "1"
    assert event.actor_label == "alice"
    assert event.occurred_at is not None
    assert event.canonical_bytes


async def test_record_event_does_not_commit_the_caller_session(session: AsyncSession) -> None:
    await record_event(session, "auth.login", outcome=AuditOutcome.SUCCESS, actor=ACTOR)
    await session.rollback()

    assert (await session.exec(select(AuditEvent))).all() == []


async def test_unknown_event_type_raises(session: AsyncSession) -> None:
    with pytest.raises(UnknownAuditEventTypeError):
        await record_event(session, "nope.never", outcome=AuditOutcome.SUCCESS, actor=ACTOR)


async def test_request_context_enriches_the_event(session: AsyncSession) -> None:
    context = AuditContext(
        request_id="req-1",
        request_ip="9.9.9.9",
        user_agent="pytest-agent",
        source=AuditSource.CHAT,
        actor=ACTOR,
    )
    with audit_context(context):
        await record_event(session, "auth.login", outcome=AuditOutcome.SUCCESS)
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.request_id == "req-1"
    assert event.request_ip == "9.9.9.9"
    assert event.user_agent == "pytest-agent"
    assert event.source == "chat"
    assert event.actor_id == "1"


async def test_explicit_actor_overrides_context_actor(session: AsyncSession) -> None:
    context = AuditContext(actor=UserActor(id="1", label="alice"))
    with audit_context(context):
        await record_event(
            session,
            "auth.login",
            outcome=AuditOutcome.FAILURE,
            actor=AnonymousActor(label="mallory"),
        )
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.actor_type == "anonymous"
    assert event.actor_id is None
    assert event.actor_label == "mallory"


async def test_event_without_actor_records_anonymous(session: AsyncSession) -> None:
    await record_event(session, "auth.login", outcome=AuditOutcome.FAILURE)
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.actor_type == "anonymous"
    assert event.actor_id is None


async def test_secret_payloads_are_redacted_before_persistence(session: AsyncSession) -> None:
    await record_event(
        session,
        "auth.login",
        outcome=AuditOutcome.SUCCESS,
        actor=ACTOR,
        tool_args={"auth": {"api_token": "s3cret"}, "course_id": 5},
        new_values={"password": "hunter2", "name": "n"},
    )
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.tool_args == {"auth": REDACTED, "course_id": 5}
    assert event.new_values == {"password": REDACTED, "name": "n"}


async def test_canonical_bytes_are_reproducible(session: AsyncSession) -> None:
    occurred_at = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
    await record_event(
        session,
        "auth.login",
        outcome=AuditOutcome.SUCCESS,
        actor=ACTOR,
        occurred_at=occurred_at,
    )
    await session.commit()

    event = (await session.exec(select(AuditEvent))).one()
    assert event.canonical_bytes == canonicalize(
        {
            "event_type": "auth.login",
            "occurred_at": "2026-07-03T12:00:00+00:00",
            "source": "system",
            "actor": {"type": "user", "id": "1", "label": "alice"},
            "outcome": "success",
            "target": {"type": None, "id": None},
            "error_detail": None,
            "old_values": None,
            "new_values": None,
            "tool": {"name": None, "args": None},
            "model": {"provider": None, "name": None, "version": None},
            "purpose": None,
        }
    )


async def test_record_event_now_commits_standalone(session: AsyncSession) -> None:
    await record_event_now("auth.login", outcome=AuditOutcome.FAILURE, actor=ACTOR)

    event = (await session.exec(select(AuditEvent))).one()
    assert event.outcome == "failure"
