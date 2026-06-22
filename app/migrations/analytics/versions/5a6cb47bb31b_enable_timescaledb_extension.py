"""enable timescaledb extension

Revision ID: 5a6cb47bb31b
Revises:
Create Date: 2026-06-19 11:44:12.522367

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a6cb47bb31b"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # TimescaleDB is a Postgres-only extension; skip on SQLite (tests).
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS timescaledb")
