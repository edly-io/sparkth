"""Users API package: exports the users router and maps a missing user to 404."""

from fastapi import status

from sparkth.api.v1.users.routes import router
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.services.users.exceptions import UserNotFound

register_exception_handler(UserNotFound, status.HTTP_404_NOT_FOUND)

__all__ = ["router"]
