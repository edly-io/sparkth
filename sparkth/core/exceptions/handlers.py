"""Exception → HTTP response registry (implementation).

This module was generated with LLM (Claude) assistance.

Core and plugins map a domain exception class to an HTTP status here;
``sparkth.main.assemble_app`` wires the registry onto the app at startup. Import the
public surface from ``sparkth.lib.exceptions.handlers``, never from this module.
"""

from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ExceptionHandler

from sparkth.lib.hooks import KeyedItemHook

__all__ = [
    "EXCEPTION_HANDLERS",
    "register_exception_handler",
]

# The single registry of exception type -> HTTP handler. Each entry is an
# ``(exc_type, handler)`` pair keyed on ``exc_type`` (KeyedItemHook derives the key from
# the entry), so a second registration for the same type raises ``ValueError``. Ships
# empty; core and plugins populate it at import/plugin-load time.
EXCEPTION_HANDLERS: KeyedItemHook[type[Exception], tuple[type[Exception], ExceptionHandler]] = KeyedItemHook(
    key=lambda entry: entry[0]
)


def register_exception_handler(exc_type: type[Exception], status_code: int) -> None:
    """Map ``exc_type`` (and, via MRO, its subclasses) to HTTP ``status_code``.

    Registers a handler on the global ``EXCEPTION_HANDLERS`` registry that renders the
    exception as ``{"detail": str(exc)}``. A second registration for the same type raises
    ``ValueError``.
    """

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    EXCEPTION_HANDLERS.add_item((exc_type, handler))
