"""Plugin preference API package.

Lets users manage their preferences (enable/disable, configure) for the plugins they may use,
and lets holders of the plugin management permission switch a plugin on or off for everyone.

Exports the router and registers the plugin configuration errors' mappings to HTTP statuses.
Core registers at import time; ``sparkth.main.assemble_app`` wires the registry onto the app
at startup (Starlette dispatches by MRO).
"""

from fastapi import status

from sparkth.api.v1.plugins.routes import router
from sparkth.core.plugins.exceptions import ConfigValidationError, PluginConfigUnavailable, PluginDisabledError
from sparkth.lib.exceptions.handlers import register_exception_handler

register_exception_handler(PluginDisabledError, status.HTTP_409_CONFLICT)
register_exception_handler(ConfigValidationError, status.HTTP_400_BAD_REQUEST)
register_exception_handler(PluginConfigUnavailable, status.HTTP_500_INTERNAL_SERVER_ERROR)

__all__ = ["router"]
