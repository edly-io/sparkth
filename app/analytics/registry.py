"""Event schema registry for the analytics emission gateway.

Maps a versioned event type — ``(event_type, version)`` — to the Pydantic schema
that validates that event's payload. The gateway resolves the schema here before
validating and landing an event, so adding a new event type is a registry entry,
not a new route.

Event types are plain strings, not a closed enum, so producers outside the core
(plugins) can register their own events without editing core. The string is the
canonical dot-separated name stored in ``raw_events.event_type``.
"""

from pydantic import BaseModel

from app.analytics.exceptions import UnknownEventTypeError


class EventRegistry:
    """In-memory registry of versioned event payload schemas."""

    def __init__(self) -> None:
        self._schemas: dict[tuple[str, int], type[BaseModel]] = {}

    def register(self, event_type: str, version: int, schema: type[BaseModel]) -> None:
        """Register ``schema`` as the validator for ``(event_type, version)``."""
        self._schemas[(event_type, version)] = schema

    def resolve(self, event_type: str, version: int) -> type[BaseModel]:
        """Return the schema for ``(event_type, version)``.

        Raises:
            UnknownEventTypeError: No schema is registered for the pair.
        """
        try:
            return self._schemas[(event_type, version)]
        except KeyError:
            raise UnknownEventTypeError(event_type, version) from None


# Module-level singleton every schema registers on (see app/analytics/schemas/).
event_registry = EventRegistry()
