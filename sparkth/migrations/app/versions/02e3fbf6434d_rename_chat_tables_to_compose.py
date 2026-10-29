"""rename chat tables to compose

Revision ID: 02e3fbf6434d
Revises: fd29c3a6164d
Create Date: 2026-10-29 14:55:39.527094

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02e3fbf6434d"
down_revision: Union[str, Sequence[str], None] = "fd29c3a6164d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = {
    "chat_conversations": "compose_conversations",
    "chat_messages": "compose_messages",
    "chat_conversation_attachments": "compose_conversation_attachments",
}

# (column, unique) per auto-named column index; the index name embeds the table name.
INDEXES = {
    "conversations": [("uuid", True), ("user_id", False), ("llm_config_id", False)],
    "messages": [("conversation_id", False)],
}


def _rename_indexes(old_prefix: str, new_prefix: str) -> None:
    for suffix, columns in INDEXES.items():
        for column, unique in columns:
            table = f"{new_prefix}_{suffix}"
            op.drop_index(op.f(f"ix_{old_prefix}_{suffix}_{column}"), table_name=table)
            op.create_index(op.f(f"ix_{new_prefix}_{suffix}_{column}"), table, [column], unique=unique)


def upgrade() -> None:
    """Rename the chat tables and their column indexes to compose."""
    for old, new in TABLES.items():
        op.rename_table(old, new)
    _rename_indexes("chat", "compose")


def downgrade() -> None:
    """Restore the chat table and index names."""
    for old, new in TABLES.items():
        op.rename_table(new, old)
    _rename_indexes("compose", "chat")
