"""Domain exceptions for the analytics subsystem."""


class UnknownEventTypeError(Exception):
    """Raised when an ``(event_type, version)`` pair has no registered schema."""

    def __init__(self, event_type: str, version: int) -> None:
        self.event_type = event_type
        self.version = version
        super().__init__(f"No schema registered for event '{event_type}' version {version}")
