"""Audit event type registry.

Mirrors the analytics :class:`~app.core.analytics.registry.EventRegistry`: a
singleton mapping event-type strings to definitions, so the taxonomy is
explicit and recording a mistyped event type fails loudly. Event types are
plain ``category.action`` strings, not a closed enum, so plugins can register
their own without editing core.
"""

from dataclasses import dataclass

from app.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError


@dataclass(frozen=True, slots=True)
class AuditEventDefinition:
    """One entry in the audit taxonomy.

    ``fail_open`` opts a read-class event type out of the default fail-closed
    write semantics: mutating and AI event types must keep the default
    ``False``.
    """

    event_type: str
    fail_open: bool = False

    def __post_init__(self) -> None:
        category, _, action = self.event_type.partition(".")
        if not category or not action:
            raise ValueError(f"Audit event type must be 'category.action', got '{self.event_type}'")

    @property
    def category(self) -> str:
        return self.event_type.partition(".")[0]

    @property
    def action(self) -> str:
        return self.event_type.partition(".")[2]


class AuditEventRegistry:
    """In-memory singleton registry of audit event definitions.

    Core event types are registered on first construction; plugin
    contributions can be registered during plugin load.
    """

    _instance: "AuditEventRegistry | None" = None

    def __new__(cls) -> "AuditEventRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # __init__ runs on every AuditEventRegistry() call, even when __new__
        # returns the existing singleton, so guard against re-construction
        # wiping registrations.
        if not hasattr(self, "_definitions"):
            self._definitions: dict[str, AuditEventDefinition] = {}
            self._register_core_events()

    def _register_core_events(self) -> None:
        self.register(AuditEventDefinition(event_type="auth.login"))

    def register(self, definition: AuditEventDefinition) -> None:
        """Register ``definition`` under its event type.

        Idempotent for an equal definition; a *different* definition claiming
        an already-registered event type raises
        :class:`DuplicateAuditEventTypeError`.
        """
        existing = self._definitions.get(definition.event_type)
        if existing is not None and existing != definition:
            raise DuplicateAuditEventTypeError(definition.event_type)
        self._definitions[definition.event_type] = definition

    def resolve(self, event_type: str) -> AuditEventDefinition:
        """Return the definition for ``event_type``.

        Raises:
            UnknownAuditEventTypeError: No definition is registered.
        """
        try:
            return self._definitions[event_type]
        except KeyError:
            raise UnknownAuditEventTypeError(event_type) from None
