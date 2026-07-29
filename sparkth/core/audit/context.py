"""Per-request audit context plumbing.

The ASGI middleware seeds an
:class:`~sparkth.core.audit.types.AuditRequestContext` into a contextvar at
the edge, so deep call sites (tool executors, services) can attribute events
to an actor and a request origin without threading a request object through
every layer. Code that runs outside a request (background tasks, CLI) either
sees an empty :class:`~sparkth.core.audit.types.AuditSystemContext` or
installs its own via :func:`audit_context`. The AI seams layer
:func:`ai_audit_context` on top to stamp their surface and driving model.
The context and actor dataclasses themselves live in
:mod:`sparkth.core.audit.types`.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from typing import Iterator

from sparkth.core.audit.enums import AuditSource
from sparkth.core.audit.types import AuditActor, AuditContext, AuditModelInfo, AuditSystemContext

_audit_context: ContextVar[AuditContext | None] = ContextVar("audit_context", default=None)

# Which model is driving the tool calls currently executing. Seeded by the
# AI seams (the chat provider loop, the RAG agent runner) via ai_audit_context
# and read by the audited tool wrapper, so model identity reaches the event
# without threading provider objects through every tool handler.
_model_info: ContextVar[AuditModelInfo | None] = ContextVar("audit_model_info", default=None)


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


def current_model_info() -> AuditModelInfo | None:
    """Return the model identity seeded by the innermost :func:`ai_audit_context`."""
    return _model_info.get()


@contextmanager
def ai_audit_context(source: AuditSource | None = None, model: AuditModelInfo | None = None) -> Iterator[None]:
    """Attribute tool executions in the enclosed block to an AI surface.

    Derives the active context with ``source`` replaced (keeping the request
    origin and resolved actor) and pins ``model`` as the identity the audited
    tool wrapper records. The chat provider loop installs
    ``(CHAT, provider/model/version)`` around its tool executions and the RAG
    agent runner installs ``(RAG, best-effort model)`` around the agent run;
    handlers themselves stay seam-agnostic.
    """
    context = current_audit_context()
    if source is not None:
        context = replace(context, source=source)
    model_token = _model_info.set(model)
    try:
        with audit_context(context):
            yield
    finally:
        _model_info.reset(model_token)


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
