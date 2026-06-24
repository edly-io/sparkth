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
    """In-memory registry of versioned event payload schemas.

    Singleton: ``EventRegistry()`` always returns the same instance, so every
    import path shares one set of registered schemas. Core default events are
    registered on first construction; call ``EventRegistry()`` during app
    assembly (``assemble_app``) to ensure the registry is ready before the
    first request arrives.
    """

    _instance: "EventRegistry | None" = None

    def __new__(cls) -> "EventRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # __init__ runs on every EventRegistry() call, even when __new__ returns
        # the existing singleton — guard so re-construction never wipes registrations.
        if not hasattr(self, "_schemas"):
            self._schemas: dict[tuple[str, int], type[BaseModel]] = {}
            self._register_defaults()

    def _register_defaults(self) -> None:
        """Register core events shipped with Sparkth."""
        # Lazy import avoids a module-level dependency from registry → schemas.
        from app.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn

        self.register("assessment.submitted", 1, AssessmentSubmitted)
        self.register("user.logged_in", 1, UserLoggedIn)

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
