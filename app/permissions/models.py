"""Scoped-RBAC table models. Authored with LLM (Claude) assistance."""

from sqlalchemy import CheckConstraint, Index, text
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
        # A scope is the pair (scope_type, scope_id): the global scope carries no
        # id, every other scope must name one. Enforced in the database so no code
        # path can persist a contradictory pair.
        CheckConstraint(
            f"(scope_type = '{SCOPE_GLOBAL}' AND scope_id IS NULL) "
            f"OR (scope_type != '{SCOPE_GLOBAL}' AND scope_id IS NOT NULL)",
            name="ck_role_assignment_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role_id: int = Field(foreign_key="role.id", index=True)
    scope_type: str = Field(max_length=50, index=True)
    scope_id: str | None = Field(max_length=100, index=True)
