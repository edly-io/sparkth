"""Email-whitelist API package.

Exports the router and registers the whitelist domain-exception → HTTP status mappings.
Core registers at import time; ``sparkth.main.assemble_app`` wires the registry onto the app
at startup (Starlette dispatches by MRO).
"""

from fastapi import status

from sparkth.api.v1.whitelist.routes import router
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.services.whitelist import (
    InvalidWhitelistValue,
    WhitelistEntryAlreadyExists,
    WhitelistEntryNotFound,
)

register_exception_handler(WhitelistEntryAlreadyExists, status.HTTP_409_CONFLICT)
register_exception_handler(WhitelistEntryNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(InvalidWhitelistValue, status.HTTP_422_UNPROCESSABLE_CONTENT)

__all__ = ["router"]
