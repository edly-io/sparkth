from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleIsBuiltin,
    RoleNotFound,
)

__all__ = [
    "GroupNotFound",
    "GroupAlreadyExists",
    "RoleNotFound",
    "RoleAlreadyExists",
    "RoleIsBuiltin",
    "PermissionNotFound",
    "PermissionScopeNotFound",
    "InvalidScopeObjectId",
]
