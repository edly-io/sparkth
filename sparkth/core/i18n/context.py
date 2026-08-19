"""Per-request locale plumbing.

Mirrors :mod:`sparkth.core.audit.context`: an ASGI middleware seeds a
contextvar at the edge and everything below reads it through an accessor.
Code that runs outside a request (background tasks, CLI) sees the platform
default, or installs its own locale via :func:`locale_context`.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from sparkth.core.config import get_settings

_locale: ContextVar[str | None] = ContextVar("locale", default=None)


def get_locale() -> str:
    """Return the active locale, or ``DEFAULT_LANGUAGE`` when none is bound."""
    locale = _locale.get()
    if locale is None:
        return get_settings().DEFAULT_LANGUAGE
    return locale


@contextmanager
def locale_context(locale: str) -> Iterator[None]:
    """Install ``locale`` as the active locale for the enclosed block.

    Used by the middleware per request, and by background tasks or tests that
    need a specific locale outside one. Callers pass a supported tag; the
    middleware validates against the allowlist before installing.
    """
    token = _locale.set(locale)
    try:
        yield
    finally:
        _locale.reset(token)


def bind_locale(tag: str) -> None:
    """Install ``tag`` as the active locale for the rest of the request.

    Mirrors :func:`sparkth.core.audit.context.bind_audit_actor`: the locale middleware
    runs before authentication, so it can only negotiate ``Accept-Language``. Once a
    signed-in user is resolved, their stored choice is the better answer and replaces the
    negotiated one — they chose it, and their browser did not.

    Deliberately not a context manager: there is nothing to restore, because the request's
    context is discarded when its task ends. This relies on the caller running in the same
    task as the route, which holds for an ``async`` FastAPI dependency but not for a sync
    one — a sync dependency runs in a threadpool with a copied context and the binding
    would be lost.
    """
    _locale.set(tag)
