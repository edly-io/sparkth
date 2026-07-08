"""Pydantic models for the role-management API."""

from typing import Self

from pydantic import BaseModel, Field, model_validator


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
    description: str | None
    permissions: list[str]


class RolePermissionAdd(BaseModel):
    permission: str = Field(min_length=1, max_length=100)
