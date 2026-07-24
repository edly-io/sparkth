"""Domain exceptions raised by the audit subsystem."""

from sparkth.core.audit.exceptions import (
    AuditCaptureError,
    DuplicateAuditEventTypeError,
    UnknownAuditEventTypeError,
)

__all__ = [
    "AuditCaptureError",
    "DuplicateAuditEventTypeError",
    "UnknownAuditEventTypeError",
]
