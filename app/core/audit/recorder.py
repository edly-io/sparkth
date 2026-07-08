"""The single write path into ``audit_events``.

Failure semantics (NIST AU-5): :func:`record_event` joins the
caller's session so a mutation and its audit record commit or roll back
together, and it never swallows errors: an audit write failure propagates and
fails the audited action (fail-closed). Event types registered with
``fail_open=True`` are the caller's signal that log-and-continue is acceptable;
the recorder itself still raises, and the call site decides.
"""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit.canonical import canonicalize
from app.core.audit.context import AnonymousActor, current_audit_context
from app.core.audit.events import AUDIT_EVENTS, BaseAuditEvent
from app.core.audit.models import AuditEvent
from app.core.audit.redaction import redact
from app.lib.db import session_scope
from app.models.base import utc_now

_ANONYMOUS = AnonymousActor()


async def record_event(session: AsyncSession, event: BaseAuditEvent) -> AuditEvent:
    """Validate, redact, canonicalize, and stage ``event`` on ``session``.

    The row is added and flushed but **not committed**: it belongs to the
    caller's transaction, so the audited mutation and its record are atomic.
    Origin metadata (request id/IP/user agent/source) and the default actor
    come from the active :class:`~app.core.audit.context.AuditContext`; an
    actor set on ``event`` overrides the context actor.

    Raises:
        UnknownAuditEventTypeError: ``event``'s class is not registered on
            :data:`~app.core.audit.events.AUDIT_EVENTS`.
        sqlalchemy.exc.SQLAlchemyError: The flush failed; the caller must let
            this fail the audited action unless the event type is fail-open.
    """
    AUDIT_EVENTS.require(type(event))
    context = current_audit_context()
    actor = event.actor or context.actor or _ANONYMOUS
    occurred_at = event.occurred_at or utc_now()
    change, target, tool, model = event.change, event.target, event.tool, event.model
    redacted_old = redact(change.old) if change is not None and change.old is not None else None
    redacted_new = redact(change.new) if change is not None and change.new is not None else None
    redacted_args = redact(tool.args) if tool is not None and tool.args is not None else None

    canonical_bytes = canonicalize(
        {
            "event_type": event.event_type,
            "occurred_at": occurred_at.isoformat(),
            "source": context.source.value,
            "actor": {"type": actor.type.value, "id": actor.id, "label": actor.label},
            "outcome": event.outcome.value,
            "target": {
                "type": target.type if target is not None else None,
                "id": target.id if target is not None else None,
            },
            "error_detail": event.error_detail,
            "old_values": redacted_old,
            "new_values": redacted_new,
            "tool": {"name": tool.name if tool is not None else None, "args": redacted_args},
            "model": {
                "provider": model.provider if model is not None else None,
                "name": model.name if model is not None else None,
                "version": model.version if model is not None else None,
            },
            "purpose": event.purpose,
        }
    )

    row = AuditEvent(
        occurred_at=occurred_at,
        category=event.category,
        action=event.action,
        source=context.source.value,
        actor_type=actor.type.value,
        actor_id=actor.id,
        actor_label=actor.label,
        request_ip=context.request_ip,
        user_agent=context.user_agent,
        request_id=context.request_id,
        outcome=event.outcome.value,
        error_detail=event.error_detail,
        target_type=target.type if target is not None else None,
        target_id=target.id if target is not None else None,
        old_values=redacted_old,
        new_values=redacted_new,
        tool_name=tool.name if tool is not None else None,
        tool_args=redacted_args,
        model_provider=model.provider if model is not None else None,
        model_name=model.name if model is not None else None,
        model_version=model.version if model is not None else None,
        purpose=event.purpose,
        canonical_bytes=canonical_bytes,
    )
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
