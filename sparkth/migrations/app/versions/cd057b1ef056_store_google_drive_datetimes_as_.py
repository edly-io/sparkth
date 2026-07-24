"""store google drive datetimes as timestamptz

Revision ID: cd057b1ef056
Revises: 29952e6a4b1b
Create Date: 2026-07-24 16:26:08.657815

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd057b1ef056"
down_revision: Union[str, Sequence[str], None] = "29952e6a4b1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs written with timezone-aware UTC datetimes; asyncpg
# rejects aware values on TIMESTAMP WITHOUT TIME ZONE columns.
_DRIVE_DATETIME_COLUMNS = (
    ("drive_oauth_tokens", "token_expiry"),
    ("drive_folders", "last_synced_at"),
    ("drive_files", "last_synced_at"),
    ("drive_files", "modified_time"),
)


def upgrade() -> None:
    """Convert Drive datetime columns to timestamptz (PostgreSQL only).

    Stored naive values are interpreted as UTC — every writer stores UTC.
    SQLite has no timestamptz, so no DDL is needed there.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column in _DRIVE_DATETIME_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE USING {column} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    """Restore Drive datetime columns to naive timestamps holding UTC values."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, column in _DRIVE_DATETIME_COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE "
            f"USING {column} AT TIME ZONE 'UTC'"
        )
