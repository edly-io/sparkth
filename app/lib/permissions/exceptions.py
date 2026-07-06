from app.core.permissions.exceptions import (
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleInUse,
    RoleNotFound,
)

__all__ = [
    "RoleNotFound",
    "RoleAlreadyExists",
    "RoleInUse",
    "PermissionNotFound",
    "PermissionScopeNotFound",
]
