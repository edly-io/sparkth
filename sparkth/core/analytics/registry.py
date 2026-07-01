"""Event schema registry for the analytics emission gateway.

Maps a versioned event type — ``(event_type, version)`` — to the
:class:`~sparkth.core.analytics.schemas.AnalyticsEventSchema` subclass that
validates that event's payload. The gateway resolves the schema here (by string)
before validating and landing an event, so adding a new event type is a registry
entry, not a new route.

Event types are plain strings, not a closed enum, so producers outside the core
(plugins) can register their own events without editing core. Each schema owns
its identity and emission policy, so registration takes the class alone.
"""

from sparkth.core.analytics.exceptions import DuplicateEventTypeError, UnknownEventTypeError
from sparkth.core.analytics.schemas import AnalyticsEventSchema


class EventRegistry:
    """In-memory registry of versioned event payload schemas.

    Singleton: ``EventRegistry()`` always returns the same instance, so every
    import path shares one set of registered schemas. Core events are registered
    on first construction; call ``EventRegistry()`` during app assembly
    (``assemble_app``) to ensure the registry is ready before the first request
    arrives.
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
            self._schemas: dict[tuple[str, int], type[AnalyticsEventSchema]] = {}
            self._server_only: dict[tuple[str, int], bool] = {}
            self._register_core_events()

    def _register_core_events(self) -> None:
        """Register core events shipped with Sparkth."""
        # Lazy import avoids a module-level dependency from registry → schemas.
        from sparkth.core.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn

        self.register(AssessmentSubmitted)
        self.register(UserLoggedIn)

    def register(self, schema: type[AnalyticsEventSchema]) -> None:
        """Register ``schema`` under its own ``(event_type, version)``.

        Idempotent: registering the same class again is a no-op, so draining the
        plugin hook more than once is safe. A *different* class claiming an
        already-registered ``(event_type, version)`` raises
        :class:`DuplicateEventTypeError`.

        Raises:
            TypeError: ``schema`` does not declare both ``event_type`` and ``version``
                as class attributes.
        """
        missing = [attr for attr in ("event_type", "version") if not hasattr(schema, attr)]
        if missing:
            raise TypeError(
                f"{schema.__qualname__} must declare {missing} as class attributes before it can be registered"
            )
        key = (schema.event_type, schema.version)
        existing = self._schemas.get(key)
        if existing is not None and existing is not schema:
            raise DuplicateEventTypeError(schema.event_type, schema.version)
        self._schemas[key] = schema
        self._server_only[key] = schema.server_only

    def resolve(self, event_type: str, version: int) -> type[AnalyticsEventSchema]:
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
