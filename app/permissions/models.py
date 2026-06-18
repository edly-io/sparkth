"""Scoped-RBAC table models. Authored with LLM (Claude) assistance."""

from sqlalchemy import Index, text
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
    __table_args__ = (
        # At most one active assignment per (user, role, scope). scope_id is
        # NULL for global scope, and SQL treats NULLs as distinct, so coalesce
        # collapses it to '' to make global rows collide too.
        Index(
            "uq_role_assignment_active",
            "user_id",
            "role_id",
            "scope_type",
            text("coalesce(scope_id, '')"),
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role_id: int = Field(foreign_key="role.id", index=True)
    scope_type: str = Field(default=SCOPE_GLOBAL, max_length=50, index=True)
    scope_id: str | None = Field(default=None, max_length=100, index=True)
