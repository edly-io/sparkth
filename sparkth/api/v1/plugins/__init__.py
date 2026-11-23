"""Plugin preference API package.

Lets users manage their preferences (enable/disable, configure) for the plugins they may use.

Exports the router. The package has no domain exceptions of its own, so nothing is
registered with the exception-handler registry here.
"""

from sparkth.api.v1.plugins.routes import router

__all__ = ["router"]
