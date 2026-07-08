"""Domain exceptions raised by the audit subsystem."""

from app.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError

__all__ = [
    "DuplicateAuditEventTypeError",
    "UnknownAuditEventTypeError",
]
