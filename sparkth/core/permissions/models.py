"""Scoped-RBAC table models. Authored with LLM (Claude) assistance."""

from sqlalchemy import Index, text
from sqlmodel import Field

from sparkth.core.models.base import SoftDeleteModel, TimestampedModel


class Role(TimestampedModel, table=True):
    __tablename__ = "role"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: str | None = Field(default=None, max_length=255)


class RolePermission(TimestampedModel, table=True):
    """Bridge table between Role and Permissions to cater the many-to-many relation."""

    __tablename__ = "role_permission"

    role_id: int = Field(foreign_key="role.id", primary_key=True)
    permission: str = Field(max_length=100, primary_key=True)


class RoleAssignment(TimestampedModel, SoftDeleteModel, table=True):
    __tablename__ = "role_assignment"
    __table_args__ = (
        # At most one active assignment per (user, role, scope). scope_object_id is
        # NULL for objectless scopes, and SQL treats NULLs as distinct, so coalesce
        # collapses it to '' to make those rows collide too.
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
        # The (scope, scope_object_id) pairing — objectless scopes name no object, others
        # must — is enforced in application code (assign_role), not a DB CHECK, so the
        # database stays ignorant of the scope vocabulary declared via PERMISSION_SCOPES.
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


class Group(TimestampedModel, table=True):
    """A flat, named set of users — the second assignee source for role grants.

    ``group`` is a reserved SQL word, so the table is ``user_group``.
    """

    __tablename__ = "user_group"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    description: str | None = Field(default=None, max_length=255)


class GroupMembership(TimestampedModel, SoftDeleteModel, table=True):
    """A user's membership in a group. Soft-deleted on removal so access history stays auditable."""

    __tablename__ = "group_membership"
    __table_args__ = (
        # At most one active membership per (user, group).
        Index(
            "uq_group_membership_active",
            "user_id",
            "group_id",
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    group_id: int = Field(foreign_key="user_group.id", index=True)
    # Provenance of the row: "manual" rows are managed by administrators; "rule" rows will be
    # owned by rule-driven membership recompute once dynamic membership lands, which must never
    # touch manual rows (and vice versa).
    source: str = Field(default="manual", max_length=20)


class GroupRoleAssignment(TimestampedModel, SoftDeleteModel, table=True):
    """A role granted to every member of a group at a scope.

    Mirrors ``RoleAssignment`` with the group as the assignee; the read-side checks resolve
    it through the same scope chain.
    """

    __tablename__ = "group_role_assignment"
    __table_args__ = (
        # At most one active assignment per (group, role, scope); coalesce collapses the
        # NULL object id of objectless scopes so those rows collide too.
        Index(
            "uq_group_role_assignment_active",
            "group_id",
            "role_id",
            "scope",
            text("coalesce(scope_object_id, '')"),
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="user_group.id", index=True)
    role_id: int = Field(foreign_key="role.id", index=True)
    scope: str = Field(max_length=50, index=True)
    scope_object_id: str | None = Field(max_length=100, index=True)
