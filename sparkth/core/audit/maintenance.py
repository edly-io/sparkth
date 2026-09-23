"""The two sanctioned writes past the append-only guard: retention and erasure.

Retention (NIST AU-11, EU AI Act Art. 19) is a per-category window configured by
``AUDIT_RETENTION_DAYS`` and ``AUDIT_RETENTION_OVERRIDES``; :func:`purge_expired_events`
deletes whole rows past it. Erasure (GDPR Art. 17) never deletes: :func:`erase_actor`
blanks the personal-data columns that sit outside the sealed canonical bytes
(``actor_label``, ``request_ip``, ``user_agent``) for one actor, leaving ``actor_id``
as a pseudonym that nothing resolves once the account is gone. Both run inside
:func:`append_only_unlocked` and record their own audit event in the same
transaction, so the trail explains its own gaps.

Authored with LLM (Claude) assistance.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, delete, text, update
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.events import ActorErasedAuditEvent, RetentionPurgedAuditEvent
from sparkth.core.audit.models import APPEND_ONLY_RELOCK_DDL, APPEND_ONLY_UNLOCK_DDL, AuditEvent
from sparkth.core.audit.recorder import record_event
from sparkth.core.audit.types import AuditChange, AuditTarget, SystemActor
from sparkth.core.config import get_settings
from sparkth.core.models.base import utc_now
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

# Key under which the default retention (every category without an override) is
# reported by purge_expired_events and named in its audit event.
DEFAULT_RETENTION_KEY = "*"

MAINTENANCE_ACTOR = SystemActor(label="audit-maintenance")


@asynccontextmanager
async def append_only_unlocked(session: AsyncSession) -> AsyncIterator[None]:
    """Let ``session``'s current transaction update or delete ``audit_events``.

    The unlock lasts for the block; the guard is re-armed on the way out even if
    the block raises, and the caller still owns the commit.
    """
    dialect = session.bind.dialect.name if session.bind is not None else ""
    for statement in APPEND_ONLY_UNLOCK_DDL.get(dialect, []):
        await session.execute(text(statement))
    try:
        yield
    finally:
        for statement in APPEND_ONLY_RELOCK_DDL.get(dialect, []):
            await session.execute(text(statement))


async def purge_expired_events() -> dict[str, int]:
    """Delete audit events older than their category's retention window.

    Each override category is purged against its own window, then everything else
    against ``AUDIT_RETENTION_DAYS``; a window of 0 keeps that slice forever. One
    ``audit.retention_purged`` event is recorded per slice that lost rows, in the
    same transaction. Returns ``{category: deleted_rows}`` for those slices
    (:data:`DEFAULT_RETENTION_KEY` for the default policy).
    """
    settings = get_settings()
    now = utc_now()
    overrides = settings.AUDIT_RETENTION_OVERRIDES
    # ponytail: one DELETE per slice, however large. Batch it if a first purge over
    # years of backlog ever holds row locks long enough to matter.
    slices: list[tuple[str, int, ColumnElement[bool]]] = [
        (category, days, col(AuditEvent.category) == category) for category, days in overrides.items()
    ]
    slices.append((DEFAULT_RETENTION_KEY, settings.AUDIT_RETENTION_DAYS, col(AuditEvent.category).not_in(overrides)))

    deleted: dict[str, int] = {}
    async with session_scope() as session:
        async with append_only_unlocked(session):
            for category, days, predicate in slices:
                if days <= 0:
                    continue
                cutoff = now - timedelta(days=days)
                result = cast(
                    CursorResult[Any],
                    await session.execute(delete(AuditEvent).where(predicate, col(AuditEvent.occurred_at) < cutoff)),
                )
                if result.rowcount:
                    deleted[category] = result.rowcount
        for category, rows in deleted.items():
            days = overrides.get(category, settings.AUDIT_RETENTION_DAYS)
            await record_event(
                session,
                RetentionPurgedAuditEvent(
                    outcome=AuditOutcome.SUCCESS,
                    actor=MAINTENANCE_ACTOR,
                    target=AuditTarget(type="audit_category", id=category),
                    change=AuditChange(old={"category": category, "retention_days": days, "deleted_rows": rows}),
                ),
            )
        await session.commit()
    logger.info("Audit retention purge deleted %s", deleted or "nothing")
    return deleted


async def erase_actor(user_id: int) -> int:
    """Blank the personal data recorded about ``user_id`` across the trail.

    Nulls ``actor_label``, ``request_ip`` and ``user_agent`` on every event the user
    performed; the sealed content, and ``actor_id`` as a pseudonym, stay. Records an
    ``audit.actor_erased`` event in the same transaction and returns the number of
    rows blanked. Deleting or anonymizing the account itself is the caller's job.
    """
    actor_id = str(user_id)
    async with session_scope() as session:
        async with append_only_unlocked(session):
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(AuditEvent)
                    .where(col(AuditEvent.actor_id) == actor_id)
                    .values(actor_label=None, request_ip=None, user_agent=None, updated_at=utc_now())
                ),
            )
        rows: int = result.rowcount
        await record_event(
            session,
            ActorErasedAuditEvent(
                outcome=AuditOutcome.SUCCESS,
                actor=MAINTENANCE_ACTOR,
                target=AuditTarget(type="user", id=actor_id),
                change=AuditChange(old={"rows": rows}),
            ),
        )
        await session.commit()
    logger.info("Audit erasure for user %s blanked %d rows", actor_id, rows)
    return rows
