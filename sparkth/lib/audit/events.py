"""Audit event classes, their envelope value objects, and outcomes.

Subclass :class:`BaseAuditEvent` to declare a new event type and register it
on the hook from :mod:`app.lib.audit.hooks`.
"""

from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.events import BaseAuditEvent, LoginAuditEvent
from sparkth.core.audit.types import AuditChange, AuditModelInfo, AuditTarget, AuditToolCall

__all__ = [
    "AuditChange",
    "AuditModelInfo",
    "AuditOutcome",
    "AuditTarget",
    "AuditToolCall",
    "BaseAuditEvent",
    "LoginAuditEvent",
]
