"""Domain exceptions for the audit subsystem."""


class UnknownAuditEventTypeError(Exception):
    """Raised when an event class (or event type) is not registered.

    Recording an unregistered event is a programming error: the AUDIT_EVENTS
    hook is what makes the taxonomy explicit and reviewable, so it fails
    loudly instead of accepting a mistyped or unregistered event type.
    """

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"No audit event class registered for '{event_type}'")


class DuplicateAuditEventTypeError(Exception):
    """Raised when two different event classes claim the same event type."""

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"A different event class is already registered for audit event '{event_type}'")
