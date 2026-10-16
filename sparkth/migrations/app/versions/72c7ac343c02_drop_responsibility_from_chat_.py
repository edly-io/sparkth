"""drop responsibility from chat conversations

Revision ID: 72c7ac343c02
Revises: 68fcddaf7a5e
Create Date: 2026-10-14 17:59:13.998412

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72c7ac343c02"
down_revision: Union[str, Sequence[str], None] = "68fcddaf7a5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("chat_conversations", "responsibility")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "chat_conversations", sa.Column("responsibility", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True)
    )
