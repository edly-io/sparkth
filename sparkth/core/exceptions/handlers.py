"""Exception → HTTP response registry (implementation).

This module was generated with LLM (Claude) assistance.

Core and plugins register how a domain exception renders as an HTTP response here;
``sparkth.main.assemble_app`` wires the registry onto the app at startup. Import the
public surface from ``sparkth.lib.exceptions.handlers``, never from this module.
"""

from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ExceptionHandler

from sparkth.lib.hooks import TypeKeyedHook

__all__ = [
    "ExceptionHandler",
    "EXCEPTION_HANDLERS",
    "register_exception_handler",
    "register_status",
    "status_handler",
]

# The single registry of exception type -> HTTP handler. Ships empty; core and plugins
# populate it at import/plugin-load time. assemble_app() iterates it once at startup.
EXCEPTION_HANDLERS: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()


def register_exception_handler(
    exc_type: type[Exception],
    handler: ExceptionHandler,
    *,
    hook: TypeKeyedHook[ExceptionHandler] = EXCEPTION_HANDLERS,
) -> None:
    """Register ``handler`` as the HTTP renderer for ``exc_type`` (and, via MRO, subclasses).

    Registering a second handler for the same type raises ``ValueError``. ``hook`` defaults
    to the global registry and is injectable for tests.
    """
    hook.add_item(exc_type, handler)


def status_handler(status_code: int) -> ExceptionHandler:
    """Build a handler rendering any exception as ``{"detail": str(exc)}`` at ``status_code``."""

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def register_status(
    exc_type: type[Exception],
    status_code: int,
    *,
    hook: TypeKeyedHook[ExceptionHandler] = EXCEPTION_HANDLERS,
) -> None:
    """Shorthand: render ``exc_type`` as ``{"detail": str(exc)}`` at ``status_code``.

    Equivalent to ``register_exception_handler(exc_type, status_handler(status_code))``.
    """
    register_exception_handler(exc_type, status_handler(status_code), hook=hook)
