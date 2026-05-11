"""replace llm name unique with partial index

Revision ID: f5a347747e4b
Revises: 74afa7d018c0
Create Date: 2026-05-11 17:36:53.081359

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f5a347747e4b'
down_revision: Union[str, Sequence[str], None] = '74afa7d018c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop full unique constraint; replace with partial index covering only non-deleted rows."""
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("uq_user_llm_config_name", "llm_configs", type_="unique")
        op.execute(
            "CREATE UNIQUE INDEX uq_user_llm_config_name_active "
            "ON llm_configs (user_id, name) WHERE is_deleted = false"
        )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Restore the original full unique constraint."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_user_llm_config_name_active")
        op.create_unique_constraint("uq_user_llm_config_name", "llm_configs", ["user_id", "name"])
    # ### end Alembic commands ###
