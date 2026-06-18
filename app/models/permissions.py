"""Scoped-RBAC table models. Authored with LLM (Claude) assistance."""

from sqlmodel import Field

from app.models.base import SoftDeleteModel, TimestampedModel
from app.permissions.constants import SCOPE_GLOBAL


class Role(TimestampedModel, table=True):
    __tablename__ = "role"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: str | None = Field(default=None, max_length=255)


class RolePermission(TimestampedModel, table=True):
    __tablename__ = "role_permission"

    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission: str = Field(max_length=100, primary_key=True)


class RoleAssignment(TimestampedModel, SoftDeleteModel, table=True):
    __tablename__ = "role_assignment"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role_id: int = Field(foreign_key="role.id", index=True)
    scope_type: str = Field(default=SCOPE_GLOBAL, max_length=50, index=True)
    scope_id: str | None = Field(default=None, max_length=100, index=True)
