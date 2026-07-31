"""Organization-structure management API package.

This module was generated with LLM (Claude) assistance.

Exports the router and registers the org domain-exception → HTTP status mappings. Core
registers at import time; ``sparkth.main.assemble_app`` wires the registry onto the app at
startup (Starlette dispatches by MRO).
"""

from fastapi import status

from sparkth.api.v1.organization.routes import router
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.organization import (
    OrganizationalUnitAlreadyExists,
    OrganizationalUnitInUse,
    OrganizationalUnitNotFound,
    OrganizationCycleError,
)

register_exception_handler(OrganizationalUnitNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(OrganizationalUnitAlreadyExists, status.HTTP_409_CONFLICT)
register_exception_handler(OrganizationalUnitInUse, status.HTTP_409_CONFLICT)
register_exception_handler(OrganizationCycleError, status.HTTP_409_CONFLICT)

__all__ = ["router"]
