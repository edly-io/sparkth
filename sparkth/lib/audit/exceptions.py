"""Domain exceptions raised by the audit subsystem."""

from sparkth.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError

__all__ = [
    "DuplicateAuditEventTypeError",
    "UnknownAuditEventTypeError",
]
