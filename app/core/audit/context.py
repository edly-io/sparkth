"""Per-request audit context.

The ASGI middleware seeds an :class:`AuditContext` into a contextvar at the
edge, so deep call sites (tool executors, services) can attribute events to an
actor and a request origin without threading a request object through every
layer. Code that runs outside a request (background tasks, CLI) either sees an
empty context or installs its own via :func:`audit_context`.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

from app.core.audit.enums import AuditSource


@dataclass(frozen=True, slots=True)
class AuditActor:
    """Who performed the action: ``type`` is user/system/anonymous."""

    type: str
    id: str | None = None
    label: str | None = None


@dataclass(slots=True)
class AuditContext:
    """Request-scoped origin metadata merged into every recorded event."""

    request_id: str | None = None
    request_ip: str | None = None
    user_agent: str | None = None
    source: AuditSource = AuditSource.SYSTEM
    actor: AuditActor | None = None


_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)


def current_audit_context() -> AuditContext:
    """Return the active context, or an empty one outside any request."""
    context = _audit_context.get()
    return context if context is not None else AuditContext()


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
        context = AuditContext()
        _audit_context.set(context)
    context.actor = actor
