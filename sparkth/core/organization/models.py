"""Organization-structure table models. Authored with LLM (Claude) assistance."""

from sqlalchemy import Index, text
from sqlmodel import Field

from sparkth.core.models.base import SoftDeleteModel, TimestampedModel


class OrganizationalUnit(TimestampedModel, table=True):
    """A node in the organization tree (university, faculty, department, …).

    Encoded as adjacency (``parent_id``) plus a materialized ``path`` of ancestor ids
    including the unit itself, root-first (``/1/7/42/``), maintained exclusively by the
    write functions in ``units.py`` — "is X a descendant of Y" is one indexable
    LIKE-prefix comparison. The tree grants nothing: no permission check reads it.
    """

    __tablename__ = "organizational_unit"
    __table_args__ = (
        # Sibling names must be unique; coalesce collapses the NULL parent_id of roots so
        # two roots with the same name collide too.
        Index(
            "uq_organizational_unit_sibling_name",
            "name",
            text("coalesce(parent_id, 0)"),
            unique=True,
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    # Display/reporting metadata ("university" | "faculty" | "department" | free-form),
    # never engine input; institutions disagree on structure, so no level enum.
    kind: str | None = Field(default=None, max_length=50)
    parent_id: int | None = Field(default=None, foreign_key="organizational_unit.id", index=True)
    path: str = Field(max_length=500, index=True)


class OrganizationMembership(TimestampedModel, SoftDeleteModel, table=True):
    """A user's seat in an organizational unit — HR truth, not a permission lever.

    Many-to-many (joint appointments are real); soft-deleted on removal so history stays
    auditable. Membership in a unit is NOT membership in its ancestors or descendants —
    whether "CS Dept staff" includes sub-units is decided later, at the rule layer.
    """

    __tablename__ = "organization_membership"
    __table_args__ = (
        # At most one active membership per (user, unit).
        Index(
            "uq_organization_membership_active",
            "user_id",
            "organizational_unit_id",
            unique=True,
            sqlite_where=text("is_deleted = 0"),
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    organizational_unit_id: int = Field(foreign_key="organizational_unit.id", index=True)
