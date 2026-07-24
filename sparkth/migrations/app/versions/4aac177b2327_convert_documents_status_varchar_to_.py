"""convert documents.status varchar to native documentstatus enum

Revision ID: 4aac177b2327
Revises: 29952e6a4b1b
Create Date: 2026-07-24 15:31:12.345762

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4aac177b2327"
down_revision: Union[str, Sequence[str], None] = "29952e6a4b1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert documents.status to the native documentstatus enum (PostgreSQL only).

    SQLite renders the enum-mapped column as plain text, so no DDL is needed there.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE TYPE documentstatus AS ENUM ('queued', 'processing', 'ready', 'failed')")
    # Stored rows use lowercase labels; normalize any stray casing so the cast cannot fail.
    op.execute("UPDATE documents SET status = lower(status) WHERE status <> lower(status)")
    # The varchar default cannot be cast in-place: drop it, retype, re-set as an enum literal.
    op.execute("ALTER TABLE documents ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE documents ALTER COLUMN status TYPE documentstatus USING status::documentstatus")
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'queued'::documentstatus")


def downgrade() -> None:
    """Restore documents.status to varchar and drop the documentstatus type."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE documents ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE documents ALTER COLUMN status TYPE character varying USING status::text")
    op.execute("ALTER TABLE documents ALTER COLUMN status SET DEFAULT 'queued'::character varying")
    op.execute("DROP TYPE documentstatus")
