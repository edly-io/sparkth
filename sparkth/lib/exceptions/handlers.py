"""Public API for the exception → HTTP mapping mechanism.

This module was generated with LLM (Claude) assistance.

Map a domain exception class to an HTTP status with ``register_exception_handler``; the
framework renders it as ``{"detail": str(exc)}`` and wires it onto the app at startup. Import
from here, never from ``sparkth.core.exceptions.handlers``. Implementation lives in
``sparkth/core/exceptions/handlers.py``.
"""

from sparkth.core.exceptions.handlers import register_exception_handler

__all__ = ["register_exception_handler"]
