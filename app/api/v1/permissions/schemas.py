"""Pydantic models for the role-management API."""

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    # Both optional: a field left unset is unchanged (PATCH semantics).
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=255)


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    permissions: list[str]


class RolePermissionAdd(BaseModel):
    permission: str = Field(min_length=1, max_length=100)
