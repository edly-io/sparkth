"""Per-request audit context.

The ASGI middleware seeds an :class:`AuditRequestContext` into a contextvar at
the edge, so deep call sites (tool executors, services) can attribute events to
an actor and a request origin without threading a request object through every
layer. Code that runs outside a request (background tasks, CLI) either sees an
empty :class:`AuditSystemContext` or installs its own via :func:`audit_context`.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import ClassVar, Iterator

from app.core.audit.enums import AuditActorType, AuditSource


@dataclass(frozen=True, slots=True)
class UserActor:
    """An authenticated identity.

    ``id`` is the immutable user ID and is mandatory: attribution must never
    hang off a mutable field. ``label`` is a display-only convenience (e.g.
    the username at the time of the event).
    """

    id: str
    label: str | None = None
    type: ClassVar[AuditActorType] = AuditActorType.USER


@dataclass(frozen=True, slots=True)
class SystemActor:
    """The platform acting on its own: scheduler, CLI, background jobs.

    There is no user behind the action, so there is no ``id``; ``label``
    names the component (e.g. ``"cli"``).
    """

    label: str | None = None
    id: ClassVar[None] = None
    type: ClassVar[AuditActorType] = AuditActorType.SYSTEM


@dataclass(frozen=True, slots=True)
class AnonymousActor:
    """An unauthenticated caller.

    ``label`` carries a *claimed*, untrusted identity (e.g. the username
    typed into a failed login); it is evidence of what was attempted, never
    an attribution, which is why the class has no ``id``.
    """

    label: str | None = None
    id: ClassVar[None] = None
    type: ClassVar[AuditActorType] = AuditActorType.ANONYMOUS


AuditActor = UserActor | SystemActor | AnonymousActor
"""Who performed the action.

A closed tagged union: each member fixes ``type`` and enforces its own field
invariants at construction, while exposing the uniform read surface
(``type``/``id``/``label``) the recorder flattens into the event row.
"""


@dataclass(slots=True, kw_only=True)
class AuditRequestContext:
    """Origin metadata for a unit of work that arrived over the network.

    Seeded by the ASGI middleware for HTTP requests (``source=REST``);
    the MCP and chat capture seams will seed their own with their source.
    ``request_id`` is mandatory (the producer generates one at the edge);
    ``request_ip`` and ``user_agent`` stay optional because a request can
    genuinely lack them.
    """

    request_id: str
    request_ip: str | None = None
    user_agent: str | None = None
    source: AuditSource = AuditSource.REST
    actor: AuditActor | None = None


@dataclass(slots=True, kw_only=True)
class AuditSystemContext:
    """Origin metadata for a unit of work with no network edge.

    CLI commands (``source=CLI``) and platform-initiated jobs carry this
    shape; it is also the empty fallback outside any installed context.
    There is no request, so the ``request_*`` fields are structurally
    absent, not merely unset.
    """

    source: AuditSource = AuditSource.SYSTEM
    actor: AuditActor | None = None
    request_id: ClassVar[None] = None
    request_ip: ClassVar[None] = None
    user_agent: ClassVar[None] = None


AuditContext = AuditRequestContext | AuditSystemContext
"""Origin metadata for the current unit of work, merged into every recorded
event.

A closed tagged union, like :data:`AuditActor`: each member carries only the
fields its origin can actually have, while exposing the uniform read surface
(``request_id``/``request_ip``/``user_agent``/``source``/``actor``) the
recorder flattens into the event row.
"""


_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def current_audit_context() -> AuditContext:
    """Return the active context, or an empty system one outside any request."""
    context = _audit_context.get()
    return context if context is not None else AuditSystemContext()


@contextmanager
def audit_context(context: AuditContext) -> Iterator[AuditContext]:
    """Install ``context`` as the active audit context for the enclosed block.

    Used by the middleware per request, and by background tasks that receive an
    explicit context snapshot from the request that spawned them.
    """
    token = _audit_context.set(context)
    try:
        yield context
    finally:
        _audit_context.reset(token)


def bind_audit_actor(actor: AuditActor) -> None:
    """Attach the resolved actor to the active context.

    Called once authentication resolves a user (the middleware runs before
    authentication, so it cannot set the actor itself). If no context is
    installed (a non-request code path), one is created so the binding is
    never silently dropped.
    """
    context = _audit_context.get()
    if context is None:
        context = AuditSystemContext()
        _audit_context.set(context)
    context.actor = actor
