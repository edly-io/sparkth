"""The single write path into ``audit_events``.

Failure semantics (NIST AU-5): :func:`record_event` joins the
caller's session so a mutation and its audit record commit or roll back
together, and it never swallows errors: an audit write failure propagates and
fails the audited action (fail-closed). Event types registered with
``fail_open=True`` are the caller's signal that log-and-continue is acceptable;
the recorder itself still raises, and the call site decides.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.context import current_audit_context
from sparkth.core.audit.events import AUDIT_EVENTS, BaseAuditEvent
from sparkth.core.audit.models import AuditEvent
from sparkth.lib.db import session_scope


async def record_event(session: AsyncSession, event: BaseAuditEvent) -> AuditEvent:
    """Validate ``event`` and stage its row on ``session``.

    Row assembly (actor and timestamp resolution, redaction, canonical bytes,
    flattening) lives in :meth:`AuditEvent.from_event`; this function owns the
    write policy. The row is added and flushed but **not committed**: it
    belongs to the caller's transaction, so the audited mutation and its
    record are atomic. Origin metadata and the default actor come from the
    active audit context; an actor set on ``event`` overrides the context
    actor.

    Raises:
        UnknownAuditEventTypeError: ``event``'s class is not registered on
            :data:`~sparkth.core.audit.events.AUDIT_EVENTS`.
        sqlalchemy.exc.SQLAlchemyError: The flush failed; the caller must let
            this fail the audited action unless the event type is fail-open.
    """
    AUDIT_EVENTS.require(type(event))
    row = AuditEvent.from_event(event, current_audit_context())
    session.add(row)
    await session.flush()
    return row


async def record_event_now(event: BaseAuditEvent) -> AuditEvent:
    """Record and commit ``event`` in its own transaction, immediately.

    For events that must survive a request that goes on to fail or roll back:
    a failed login must be on record even though the request ends in a 401.
    Same fail-closed semantics as :func:`record_event`: errors propagate.
    """
    async with session_scope() as session:
        row = await record_event(session, event)
        await session.commit()
    return row
