"""Domain exceptions for the audit subsystem."""


class UnknownAuditEventTypeError(Exception):
    """Raised when an event type has no registered definition.

    Recording an unregistered event type is a programming error: the registry
    is what makes the taxonomy explicit and reviewable, so it fails loudly
    instead of accepting a mistyped category.
    """

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"No audit event definition registered for '{event_type}'")


class DuplicateAuditEventTypeError(Exception):
    """Raised when two different definitions claim the same event type."""

    def __init__(self, event_type: str) -> None:
        self.event_type = event_type
        super().__init__(f"A different definition is already registered for audit event '{event_type}'")
