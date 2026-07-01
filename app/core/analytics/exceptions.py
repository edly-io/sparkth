"""Domain exceptions for the analytics subsystem."""


class UnknownEventTypeError(Exception):
    """Raised when an ``(event_type, version)`` pair has no registered schema."""

    def __init__(self, event_type: str, version: int) -> None:
        self.event_type = event_type
        self.version = version
        super().__init__(f"No schema registered for event '{event_type}' version {version}")


class DuplicateEventTypeError(Exception):
    """Raised when two different schemas claim the same ``(event_type, version)``.

    A colliding schema class is a startup-fatal programming error — a producer's
    payload would silently validate against the wrong schema.
    """

    def __init__(self, event_type: str, version: int) -> None:
        self.event_type = event_type
        self.version = version
        super().__init__(f"A different schema is already registered for event '{event_type}' version {version}")


class EventNamespaceError(Exception):
    """Raised when a plugin contributes an event not namespaced under its own name."""

    def __init__(self, plugin_name: str, event_type: str) -> None:
        self.plugin_name = plugin_name
        self.event_type = event_type
        super().__init__(
            f"Plugin '{plugin_name}' registered event '{event_type}', which is not namespaced under '{plugin_name}.'"
        )
