from sparkth.core.permissions.exceptions import (
    GroupAlreadyExists,
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleAssignmentNotFound,
    RoleIsBuiltin,
    RoleNotFound,
)

__all__ = [
    "GroupNotFound",
    "GroupAlreadyExists",
    "RoleNotFound",
    "RoleAlreadyExists",
    "RoleAssignmentNotFound",
    "RoleIsBuiltin",
    "PermissionNotFound",
    "PermissionScopeNotFound",
    "InvalidScopeObjectId",
]
