"""let audit maintenance past the append-only guard

Revision ID: 86af5a3d3959
Revises: a282a83eec61
Create Date: 2026-09-18 15:06:45.988175

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86af5a3d3959"
down_revision: Union[str, Sequence[str], None] = "a282a83eec61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# PostgreSQL only: the trigger function from a282a83eec61 learns to stand down while the
# transaction-local setting sparkth.audit_maintenance is on (retention purge, GDPR
# erasure); TRUNCATE stays rejected. SQLite (tests) needs nothing: its maintenance path
# drops and recreates the triggers inside the transaction instead. Spelled out here, not
# imported from sparkth.core.audit.models, so a later edit to the model cannot change what
# this applied revision did.
_GATED = """CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP <> 'TRUNCATE' AND current_setting('sparkth.audit_maintenance', true) = 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_events is append-only' USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql"""

_UNGATED = """CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only' USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql"""


def upgrade() -> None:
    """Replace the guard function with the gated version (PostgreSQL only)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_GATED)


def downgrade() -> None:
    """Restore the unconditional guard function (PostgreSQL only)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_UNGATED)
