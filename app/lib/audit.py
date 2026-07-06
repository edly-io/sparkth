"""Audit trail public API: the curated surface for recording audit events.

Import the audit surface from here (``record_event``, ``record_event_now``,
the context helpers, the registry, and the enums); never import from
``app.core.audit.*`` directly. Implementation lives in :mod:`app.core.audit`.

The audit trail is the append-only system of record for who did what, when,
and with what effect. It is deliberately *not* the analytics pipeline:
analytics (:mod:`app.lib.analytics`) is best-effort and droppable, audit is
fail-closed, meaning an event that cannot be written fails the mutating or AI
action it records.
"""

from app.core.audit.context import (
    AnonymousActor,
    AuditActor,
    AuditContext,
    SystemActor,
    UserActor,
    audit_context,
    bind_audit_actor,
    current_audit_context,
)
from app.core.audit.enums import AuditActorType, AuditOutcome, AuditSource
from app.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError
from app.core.audit.middleware import AuditContextMiddleware
from app.core.audit.recorder import record_event, record_event_now
from app.core.audit.registry import AuditEventDefinition, AuditEventRegistry

__all__ = [
    "AnonymousActor",
    "AuditActor",
    "AuditActorType",
    "AuditContext",
    "AuditContextMiddleware",
    "AuditEventDefinition",
    "AuditEventRegistry",
    "AuditOutcome",
    "AuditSource",
    "DuplicateAuditEventTypeError",
    "SystemActor",
    "UnknownAuditEventTypeError",
    "UserActor",
    "audit_context",
    "bind_audit_actor",
    "current_audit_context",
    "record_event",
    "record_event_now",
]
