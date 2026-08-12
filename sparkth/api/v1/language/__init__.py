"""Supported-languages API package.

Exports the router. The package has no domain exceptions of its own, so nothing is
registered with the exception-handler registry here.
"""

from sparkth.api.v1.language.routes import router

__all__ = ["router"]
