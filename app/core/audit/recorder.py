"""The single write path into ``audit_events``.

Failure semantics (NIST AU-5): :func:`record_event` joins the
caller's session so a mutation and its audit record commit or roll back
together, and it never swallows errors: an audit write failure propagates and
fails the audited action (fail-closed). Event types registered with
``fail_open=True`` are the caller's signal that log-and-continue is acceptable;
the recorder itself still raises, and the call site decides.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit.canonical import canonicalize
from app.core.audit.context import AuditActor, current_audit_context
from app.core.audit.enums import AuditOutcome
from app.core.audit.redaction import redact
from app.core.audit.registry import AuditEventRegistry
from app.lib.db import session_scope
from app.models.audit import AuditEvent
from app.models.base import utc_now

_ANONYMOUS = AuditActor(type="anonymous")


async def record_event(
    session: AsyncSession,
    event_type: str,
    *,
    outcome: AuditOutcome,
    actor: AuditActor | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    error_detail: str | None = None,
    old_values: Mapping[str, Any] | None = None,
    new_values: Mapping[str, Any] | None = None,
    tool_name: str | None = None,
    tool_args: Mapping[str, Any] | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    purpose: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Validate, redact, canonicalize, and stage one audit event on ``session``.

    The event is added and flushed but **not committed**: it belongs to the
    caller's transaction, so the audited mutation and its record are atomic.
    Origin metadata (request id/IP/user agent/source) and the default actor
    come from the active :class:`~app.core.audit.context.AuditContext`; an
    explicit ``actor`` overrides the context actor.

    Raises:
        UnknownAuditEventTypeError: ``event_type`` is not registered.
        sqlalchemy.exc.SQLAlchemyError: The flush failed; the caller must let
            this fail the audited action unless the event type is fail-open.
    """
    definition = AuditEventRegistry().resolve(event_type)
    context = current_audit_context()
    resolved_actor = actor or context.actor or _ANONYMOUS
    resolved_occurred_at = occurred_at or utc_now()
    redacted_old = redact(old_values) if old_values is not None else None
    redacted_new = redact(new_values) if new_values is not None else None
    redacted_args = redact(tool_args) if tool_args is not None else None

    canonical_bytes = canonicalize(
        {
            "event_type": definition.event_type,
            "occurred_at": resolved_occurred_at.isoformat(),
            "source": context.source.value,
            "actor": {"type": resolved_actor.type, "id": resolved_actor.id, "label": resolved_actor.label},
            "outcome": outcome.value,
            "target": {"type": target_type, "id": target_id},
            "error_detail": error_detail,
            "old_values": redacted_old,
            "new_values": redacted_new,
            "tool": {"name": tool_name, "args": redacted_args},
            "model": {"provider": model_provider, "name": model_name, "version": model_version},
            "purpose": purpose,
        }
    )

    event = AuditEvent(
        occurred_at=resolved_occurred_at,
        category=definition.category,
        action=definition.action,
        source=context.source.value,
        actor_type=resolved_actor.type,
        actor_id=resolved_actor.id,
        actor_label=resolved_actor.label,
        request_ip=context.request_ip,
        user_agent=context.user_agent,
        request_id=context.request_id,
        outcome=outcome.value,
        error_detail=error_detail,
        target_type=target_type,
        target_id=target_id,
        old_values=redacted_old,
        new_values=redacted_new,
        tool_name=tool_name,
        tool_args=redacted_args,
        model_provider=model_provider,
        model_name=model_name,
        model_version=model_version,
        purpose=purpose,
        canonical_bytes=canonical_bytes,
    )
    session.add(event)
    await session.flush()
    return event


async def record_event_now(
    event_type: str,
    *,
    outcome: AuditOutcome,
    actor: AuditActor | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    error_detail: str | None = None,
    old_values: Mapping[str, Any] | None = None,
    new_values: Mapping[str, Any] | None = None,
    tool_name: str | None = None,
    tool_args: Mapping[str, Any] | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    purpose: str | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Record and commit one event in its own transaction, immediately.

    For events that must survive a request that goes on to fail or roll back:
    a failed login must be on record even though the request ends in a 401.
    Same fail-closed semantics as :func:`record_event`: errors propagate.
    """
    async with session_scope() as session:
        event = await record_event(
            session,
            event_type,
            outcome=outcome,
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            error_detail=error_detail,
            old_values=old_values,
            new_values=new_values,
            tool_name=tool_name,
            tool_args=tool_args,
            model_provider=model_provider,
            model_name=model_name,
            model_version=model_version,
            purpose=purpose,
            occurred_at=occurred_at,
        )
        await session.commit()
    return event
