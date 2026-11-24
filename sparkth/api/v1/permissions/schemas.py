"""Pydantic models for the permissions API: permission checks, role management and group management."""

from typing import Self

from pydantic import BaseModel, Field, model_validator


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


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)


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
    display_name: str = Field(description="The role's name as people read it, in the request's language.")
    description: str | None
    permissions: list[str]
    is_builtin: bool
    is_default: bool = Field(description="Whether every account is given this role when it is created.")
    user_count: int = Field(description="How many people hold this role directly, at any scope.")
    group_count: int = Field(description="How many groups hold this role, at any scope.")


class RolePermissionAdd(BaseModel):
    permission: str = Field(min_length=1, max_length=100)


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
