"""Current-user API package.

Exports the router and registers the self-service account domain-exception → HTTP status
mappings. Core registers at import time; ``sparkth.main.assemble_app`` wires the registry
onto the app at startup (Starlette dispatches by MRO).
"""

from fastapi import status

from sparkth.api.v1.user.routes import router
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.services.account import IncorrectPassword, PasswordNotSet

register_exception_handler(IncorrectPassword, status.HTTP_400_BAD_REQUEST)
register_exception_handler(PasswordNotSet, status.HTTP_409_CONFLICT)

__all__ = ["router"]
