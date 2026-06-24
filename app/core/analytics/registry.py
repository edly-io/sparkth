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

from app.core.analytics.exceptions import UnknownEventTypeError


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
            self._server_only: dict[tuple[str, int], bool] = {}
            self._register_defaults()

    def _register_defaults(self) -> None:
        """Register core events shipped with Sparkth."""
        # Lazy import avoids a module-level dependency from registry → schemas.
        from app.core.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn

        self.register("assessment.submitted", 1, AssessmentSubmitted, server_only=True)
        self.register("user.logged_in", 1, UserLoggedIn, server_only=True)

    def register(
        self,
        event_type: str,
        version: int,
        schema: type[BaseModel],
        *,
        server_only: bool = False,
    ) -> None:
        """Register ``schema`` as the validator for ``(event_type, version)``.

        Args:
            event_type: Dot-separated event name, e.g. ``"assessment.submitted"``.
            version: Schema version integer.
            schema: Pydantic model that validates the event payload.
            server_only: When ``True``, the event may only be emitted by trusted
                server-side callers via :func:`~app.core.analytics.gateway.ingest_event`
                directly. The HTTP emission endpoint rejects it with ``403``.
        """
        self._schemas[(event_type, version)] = schema
        self._server_only[(event_type, version)] = server_only

    def resolve(self, event_type: str, version: int) -> type[BaseModel]:
        """Return the schema for ``(event_type, version)``.

        Raises:
            UnknownEventTypeError: No schema is registered for the pair.
        """
        try:
            return self._schemas[(event_type, version)]
        except KeyError:
            raise UnknownEventTypeError(event_type, version) from None

    def is_server_only(self, event_type: str, version: int) -> bool:
        """Return whether ``(event_type, version)`` is restricted to server-side callers.

        Raises:
            UnknownEventTypeError: No schema is registered for the pair.
        """
        try:
            return self._server_only[(event_type, version)]
        except KeyError:
            raise UnknownEventTypeError(event_type, version) from None
