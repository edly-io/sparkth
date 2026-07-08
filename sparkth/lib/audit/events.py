"""Audit event classes, their envelope value objects, and outcomes.

Declare a new event type by subclassing the tier that matches its category
(:class:`BaseAuditEvent` for plain actions, :class:`MutationAuditEvent` for
state changes, :class:`AIActionAuditEvent` for AI-driven actions) and
register it on the hook from :mod:`sparkth.lib.audit.hooks`.
"""

from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.events import AIActionAuditEvent, BaseAuditEvent, LoginAuditEvent, MutationAuditEvent
from sparkth.core.audit.types import AuditChange, AuditModelInfo, AuditTarget, AuditToolCall

__all__ = [
    "AIActionAuditEvent",
    "AuditChange",
    "AuditModelInfo",
    "AuditOutcome",
    "AuditTarget",
    "AuditToolCall",
    "BaseAuditEvent",
    "LoginAuditEvent",
    "MutationAuditEvent",
]
