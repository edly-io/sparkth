"""add idempotency guards to schema fixes

Revision ID: 3623a8f30805
Revises: acc6f4381f88
Create Date: 2026-04-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3623a8f30805"
down_revision: Union[str, Sequence[str], None] = "acc6f4381f88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # These guards ensure the migration is idempotent — if a previous run
    # partially succeeded or was interrupted, we don't error on re-run.

    # Check if old idx_conversation_uuid index still exists and drop it
    indexes = [idx["name"] for idx in inspector.get_indexes("chat_conversations")]
    if "idx_conversation_uuid" in indexes:
        op.drop_index(op.f("idx_conversation_uuid"), table_name="chat_conversations")

    # Check if constraint on drive_oauth_tokens needs to be dropped
    constraints = [constraint["name"] for constraint in inspector.get_unique_constraints("drive_oauth_tokens")]
    if "drive_oauth_tokens_user_id_key" in constraints:
        op.drop_constraint(
            op.f("drive_oauth_tokens_user_id_key"),
            "drive_oauth_tokens",
            type_="unique",
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Restore constraints only if they don't exist
    constraints = [constraint["name"] for constraint in inspector.get_unique_constraints("drive_oauth_tokens")]
    if "drive_oauth_tokens_user_id_key" not in constraints:
        op.create_unique_constraint(
            op.f("drive_oauth_tokens_user_id_key"),
            "drive_oauth_tokens",
            ["user_id"],
            postgresql_nulls_not_distinct=False,
        )

    # Restore index only if it doesn't exist
    indexes = [idx["name"] for idx in inspector.get_indexes("chat_conversations")]
    if "idx_conversation_uuid" not in indexes:
        op.create_index(op.f("idx_conversation_uuid"), "chat_conversations", ["uuid"], unique=True)
