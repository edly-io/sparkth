"""Audit event classes, their envelope value objects, and outcomes.

Subclass :class:`BaseAuditEvent` to declare a new event type and register it
on the hook from :mod:`app.lib.audit.hooks`.
"""

from app.core.audit.enums import AuditOutcome
from app.core.audit.events import BaseAuditEvent, LoginAuditEvent
from app.core.audit.types import AuditChange, AuditModelInfo, AuditTarget, AuditToolCall

__all__ = [
    "AuditChange",
    "AuditModelInfo",
    "AuditOutcome",
    "AuditTarget",
    "AuditToolCall",
    "BaseAuditEvent",
    "LoginAuditEvent",
]
