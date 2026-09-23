"""protect audit_events from update and delete

Revision ID: a282a83eec61
Revises: 0a2dfb2685ad
Create Date: 2026-09-16 14:51:28.965178

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a282a83eec61"
down_revision: Union[str, Sequence[str], None] = "0a2dfb2685ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The DDL is spelled out here rather than imported from sparkth.core.audit.models on
# purpose: a migration is a point-in-time snapshot, and importing the live definition
# would let a later edit to the model silently change what this applied revision did.
# Any change to the guard belongs in a new migration; models.py keeps its own copy for
# create_all on fresh databases.
_UPGRADE: dict[str, list[str]] = {
    "postgresql": [
        """CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only' USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql""",
        """CREATE TRIGGER audit_events_no_update_delete
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()""",
        """CREATE TRIGGER audit_events_no_truncate
BEFORE TRUNCATE ON audit_events
FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()""",
    ],
    "sqlite": [
        """CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END""",
        """CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END""",
    ],
}

_DOWNGRADE: dict[str, list[str]] = {
    "postgresql": [
        "DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events",
        "DROP TRIGGER IF EXISTS audit_events_no_update_delete ON audit_events",
        "DROP FUNCTION IF EXISTS audit_events_append_only()",
    ],
    "sqlite": [
        "DROP TRIGGER IF EXISTS audit_events_no_delete",
        "DROP TRIGGER IF EXISTS audit_events_no_update",
    ],
}


def upgrade() -> None:
    """Install the triggers that reject UPDATE, DELETE, and TRUNCATE on audit_events.

    Fresh databases get the same triggers from ``create_all``; this migration installs
    them where the table already exists.
    """
    for statement in _UPGRADE[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    """Remove the append-only triggers (the rows themselves are untouched)."""
    for statement in _DOWNGRADE[op.get_bind().dialect.name]:
        op.execute(statement)
