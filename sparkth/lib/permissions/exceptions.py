from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleNotDeletable,
    RoleNotFound,
)

__all__ = [
    "GroupNotFound",
    "GroupAlreadyExists",
    "RoleNotFound",
    "RoleAlreadyExists",
    "RoleNotDeletable",
    "PermissionNotFound",
    "PermissionScopeNotFound",
    "InvalidScopeObjectId",
]
