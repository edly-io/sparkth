"""Public API for the permissions framework.

Application code and plugins import the permissions surface from here.
"""

# from app.core.permissions.constants import SCOPE_GLOBAL
from app.core.permissions import assign_role, can, revoke_role
from app.core.permissions.exceptions import RoleNotFound
from app.lib.permissions.utils import create_permisson, create_scope

__all__ = [
    "assign_role",
    "can",
    "revoke_role",
    "RoleNotFound",
    # "SCOPE_GLOBAL"
    create_permisson,
    create_scope,
]
