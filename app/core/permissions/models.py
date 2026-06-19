"""Scoped-RBAC table models. Authored with LLM (Claude) assistance."""

from sqlalchemy import CheckConstraint, Index, text
from sqlmodel import Field

from app.models.base import SoftDeleteModel, TimestampedModel


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
        # At most one active assignment per (user, role, scope). scope_object_id is
        # NULL for global scope, and SQL treats NULLs as distinct, so coalesce
        # collapses it to '' to make global rows collide too.
        Index(
            "uq_role_assignment_active",
            "user_id",
            "role_id",
            "scope",
            text("coalesce(scope_object_id, '')"),
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("is_deleted = false"),
        ),
        # A scope is the pair (scope, scope_object_id): the global scope names no
        # object, every other scope must. Enforced in the database so no code path
        # can persist a contradictory pair.
        CheckConstraint(
            "(scope = 'global' AND scope_object_id IS NULL) OR (scope != 'global' AND scope_object_id IS NOT NULL)",
            name="ck_role_assignment_scope",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role_id: int = Field(foreign_key="role.id", index=True)
    # scope is the kind of boundary (global, course, …). The set of valid kinds is
    # registered in application code via the permissions hook, not a database table,
    # so this is a free-form string rather than a foreign key.
    scope: str = Field(max_length=50, index=True)
    # scope_object_id names which entity of that kind. It is polymorphic — it points
    # at different domain tables depending on the scope — so it is deliberately not a
    # foreign key.
    scope_object_id: str | None = Field(max_length=100, index=True)
