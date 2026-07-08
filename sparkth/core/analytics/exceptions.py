"""Domain exceptions for the analytics subsystem."""


class UnknownEventTypeError(Exception):
    """Raised when an ``(event_type, version)`` pair has no registered schema."""

    def __init__(self, event_type: str, version: int) -> None:
        self.event_type = event_type
        self.version = version
        super().__init__(f"No schema registered for event '{event_type}' version {version}")


class DuplicateEventTypeError(Exception):
    """Raised when a schema claims an already-registered ``(event_type, version)``.

    Registration is not idempotent: this fires for a colliding *different* class and
    for re-registering the *same* class. Either is a startup-fatal programming error —
    a producer's payload could silently validate against the wrong schema.
    """

    def __init__(self, event_type: str, version: int) -> None:
        self.event_type = event_type
        self.version = version
        super().__init__(f"A schema is already registered for event '{event_type}' version {version}")


class EventNamespaceError(Exception):
    """Raised when a plugin contributes an event not namespaced under its own name."""

    def __init__(self, plugin_name: str, event_type: str) -> None:
        self.plugin_name = plugin_name
        self.event_type = event_type
        super().__init__(
            f"Plugin '{plugin_name}' registered event '{event_type}', which is not namespaced under '{plugin_name}.'"
        )


class ContinuousAggregateNotFound(Exception):
    """Raised when a backfill targets a continuous aggregate that does not exist."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No continuous aggregate named '{name}' exists in the analytics database")
