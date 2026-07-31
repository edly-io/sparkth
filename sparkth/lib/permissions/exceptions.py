from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupInUse,
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleInUse,
    RoleNotFound,
)

__all__ = [
    "GroupNotFound",
    "GroupAlreadyExists",
    "GroupInUse",
    "RoleNotFound",
    "RoleAlreadyExists",
    "RoleInUse",
    "PermissionNotFound",
    "PermissionScopeNotFound",
    "InvalidScopeObjectId",
]
