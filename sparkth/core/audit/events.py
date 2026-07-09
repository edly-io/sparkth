"""Self-describing audit event types.

An audit event type is a frozen dataclass subclassing :class:`BaseAuditEvent`:
the class carries its own identity (``event_type``, ``fail_open``) as
ClassVars and only grouped envelope fields, so :func:`sparkth.lib.audit.record_event`
takes the session and one event object instead of a flat argument list.

Event classes are registered on the module-level :data:`AUDIT_EVENTS` hook
(mirroring the permissions hooks and the analytics schema registry): the
taxonomy stays explicit, a duplicate event type collides loudly, and plugins
can register their own event classes without editing core. The grouped
envelope value objects live in :mod:`sparkth.core.audit.types`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, TypeVar

from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError
from sparkth.core.audit.types import AuditActor, AuditChange, AuditModelInfo, AuditTarget, AuditToolCall
from sparkth.lib.hooks import KeyedClassHook


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseAuditEvent:
    """One audit event, ready to be recorded.

    Subclass per event type, set ``event_type`` (``category.action``), and
    register the class on :data:`AUDIT_EVENTS`. ``fail_open`` opts a
    read-class event type out of the default fail-closed write semantics:
    mutating and AI event types must keep the default ``False``.

    The base carries only the fields every category has. ``actor`` and
    ``occurred_at`` are optional because the recorder resolves them (context
    actor or anonymous; current time). ``target`` is what the action acted
    on; for a failed login it carries the *claimed* username as untrusted
    evidence. Mutation snapshots live on :class:`MutationAuditEvent` and AI
    provenance on :class:`AIActionAuditEvent`, so a category never exposes
    fields it cannot have.
    """

    event_type: ClassVar[str]
    fail_open: ClassVar[bool] = False

    outcome: AuditOutcome
    actor: AuditActor | None = None
    error_detail: str | None = None
    occurred_at: datetime | None = None
    target: AuditTarget | None = None

    @property
    def category(self) -> str:
        return self.event_type.partition(".")[0]

    @property
    def action(self) -> str:
        return self.event_type.partition(".")[2]


@dataclass(frozen=True, slots=True, kw_only=True)
class MutationAuditEvent(BaseAuditEvent):
    """Base for events that change stored state.

    ``change`` carries the redactable before/after snapshots (the NIST AU-3
    "what effect" field); a denied or failed mutation may have none.
    """

    change: AuditChange | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AIActionAuditEvent(MutationAuditEvent):
    """Base for AI-driven actions (tool calls, generations).

    Extends the mutation base because AI actions often mutate; read-only AI
    actions leave ``change`` unset. ``purpose`` is reserved for FERPA
    disclosure logging.
    """

    tool: AuditToolCall | None = None
    model: AuditModelInfo | None = None
    purpose: str | None = None


E = TypeVar("E", bound=BaseAuditEvent)


class AuditEventTypeHook(KeyedClassHook[BaseAuditEvent]):
    """Hook mapping event types to their event classes.

    A :class:`sparkth.lib.hooks.KeyedClassHook` keyed by ``event_type``, adding
    the ``category.action`` format check and the audit exception types.
    """

    def register(self, event_cls: type[E]) -> type[E]:
        """Register ``event_cls`` under its event type; usable as a decorator.

        Raises:
            ValueError: ``event_type`` is not ``category.action``.
            DuplicateAuditEventTypeError: A different class already claims
                the event type.
        """
        event_type = event_cls.event_type
        category, _, action = event_type.partition(".")
        if not category or not action:
            raise ValueError(f"Audit event type must be 'category.action', got '{event_type}'")
        if not self.add_class(event_type, event_cls):
            raise DuplicateAuditEventTypeError(event_type)
        return event_cls

    def resolve(self, event_type: str) -> type[BaseAuditEvent]:
        """Return the class registered for ``event_type``.

        Raises:
            UnknownAuditEventTypeError: No class is registered.
        """
        event_cls = self.get(event_type)
        if event_cls is None:
            raise UnknownAuditEventTypeError(event_type)
        return event_cls

    def require(self, event_cls: type[BaseAuditEvent]) -> None:
        """Assert ``event_cls`` is the registered class for its event type.

        Raises:
            UnknownAuditEventTypeError: The class (or its event type) is not
                registered; recording it is a programming error.
        """
        if self.get(event_cls.event_type) is not event_cls:
            raise UnknownAuditEventTypeError(event_cls.event_type)


AUDIT_EVENTS: AuditEventTypeHook = AuditEventTypeHook()


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class LoginAuditEvent(BaseAuditEvent):
    """An authentication attempt: success, bad credentials, or denied."""

    event_type: ClassVar[str] = "auth.login"
