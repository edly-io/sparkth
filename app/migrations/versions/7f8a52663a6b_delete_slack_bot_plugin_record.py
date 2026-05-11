"""delete_slack_bot_plugin_record

Revision ID: 7f8a52663a6b
Revises: dbd647a16bf8
Create Date: 2026-04-23 15:50:05.821317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7f8a52663a6b'
down_revision: Union[str, Sequence[str], None] = 'dbd647a16bf8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove user_plugins rows referencing the legacy "slack-bot" plugin first
    # to satisfy the FK constraint before deleting the plugin row itself.
    op.execute("""
        DELETE FROM user_plugins
        WHERE plugin_id = (SELECT id FROM plugins WHERE name = 'slack-bot')
    """)
    op.execute("DELETE FROM plugins WHERE name = 'slack-bot'")


def downgrade() -> None:
    # Intentionally not reversible — deleted rows cannot be restored
    # without their original IDs and configuration data.
    pass
