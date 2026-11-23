"""rename user_plugins to user_plugin_preferences

Revision ID: a5b4a01a31ca
Revises: 4bc7a669e696
Create Date: 2026-11-23 15:14:49.622822

Authored with LLM (Claude) assistance.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b4a01a31ca"
down_revision: Union[str, Sequence[str], None] = "4bc7a669e696"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TABLE = "user_plugins"
NEW_TABLE = "user_plugin_preferences"
OLD_UNIQUE = "uq_user_plugin"
NEW_UNIQUE = "uq_user_plugin_preference"
INDEXED_COLUMNS = ("is_deleted", "plugin_id", "user_id")


def rename_preference_table(old_table: str, new_table: str, old_unique: str, new_unique: str) -> None:
    """Rename the table, then its unique constraint and its indexes, which carry the table name."""
    op.rename_table(old_table, new_table)
    with op.batch_alter_table(new_table) as batch:
        batch.drop_constraint(old_unique, type_="unique")
        batch.create_unique_constraint(new_unique, ["user_id", "plugin_id"])
        for column in INDEXED_COLUMNS:
            batch.drop_index(f"ix_{old_table}_{column}")
            batch.create_index(f"ix_{new_table}_{column}", [column], unique=False)


def upgrade() -> None:
    """Rename the per-user plugin table to user_plugin_preferences."""
    rename_preference_table(OLD_TABLE, NEW_TABLE, OLD_UNIQUE, NEW_UNIQUE)


def downgrade() -> None:
    """Rename the per-user plugin table back to user_plugins."""
    rename_preference_table(NEW_TABLE, OLD_TABLE, NEW_UNIQUE, OLD_UNIQUE)
