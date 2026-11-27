"""Pydantic models for the permissions API: permission checks, role management and group management."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from sparkth.core.permissions.enums import PermissionRisk


class PermissionCheck(BaseModel):
    """One check: does the current user hold a permission at a scope?"""

    permission: str = Field(description="Permission name to check, e.g. 'analytics.read'.")
    scope: str = Field(description="Scope kind to check at, e.g. 'global'.")
    scope_object_id: str | None = Field(
        None, description="Object id for an object-bearing scope. Omit it to ask about any object of the scope."
    )


class PermissionCheckResult(PermissionCheck):
    """A check and its answer."""

    allowed: bool


class PermissionResponse(BaseModel):
    """A permission a role can hold, with what it is for, in the request's language."""

    name: str
    label: str = Field(description="What the permission lets its holder do, e.g. 'Edit roles'.")
    description: str = Field(description="One sentence on what the permission allows.")
    category: str = Field(description="The category the permission is listed under, e.g. 'Users & access'.")
    risks: list[PermissionRisk] = Field(description="The reasons to think twice before granting the permission.")
    requires: list[str] = Field(description="The permissions a holder also needs for this one to be of use.")


class RoleCreate(BaseModel):
    """A new role: its name, description and the permissions it starts with (none by default).

    The permissions are either listed or taken from the role to duplicate, never both.
    """

    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list)
    duplicate_of: int | None = Field(
        default=None, description="The id of a role whose permissions the new role starts with."
    )

    @model_validator(mode="after")
    def _require_one_source_of_permissions(self) -> Self:
        if self.permissions and self.duplicate_of is not None:
            raise ValueError("permissions and duplicate_of cannot both be provided")
        return self


class RoleUpdate(BaseModel):
    # Both optional: a field left unset is unchanged (PATCH semantics). A fully-empty update
    # (neither field provided) is rejected by the validator below so it can't silently no-op.
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_name_or_description(self) -> Self:
        if self.name is None and self.description is None:
            raise ValueError("at least one of name or description must be provided")
        return self


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    permissions: list[str]
    is_builtin: bool
    is_default: bool = Field(description="Whether every account is given this role when it is created.")
    user_count: int = Field(description="How many people hold this role directly, at any scope.")
    group_count: int = Field(description="How many groups hold this role, at any scope.")
    risks: list[PermissionRisk] = Field(description="The reasons to think twice before giving someone this role.")


class RolePermissionsSet(BaseModel):
    """Every permission the role should grant once saved; anything else it grants is revoked."""

    permissions: list[str]


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)


class GroupUpdate(BaseModel):
    # Both optional: a field left unset is unchanged (PATCH semantics). A fully-empty update
    # (neither field provided) is rejected by the validator below so it can't silently no-op.
    # Known limitation (shared with RoleUpdate): because None means "unchanged", a description
    # can never be cleared back to null through this schema — that needs an explicit sentinel.
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _require_name_or_description(self) -> Self:
        if self.name is None and self.description is None:
            raise ValueError("at least one of name or description must be provided")
        return self


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
