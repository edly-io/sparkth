"""The hook plugins and core use to register audit event classes."""

from app.core.audit.events import AUDIT_EVENTS

__all__ = [
    "AUDIT_EVENTS",
]
