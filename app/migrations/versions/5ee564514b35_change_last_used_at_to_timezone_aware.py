"""change_last_used_at_to_timezone_aware

Revision ID: 5ee564514b35
Revises: 6cc2b7149752
Create Date: 2026-03-05 12:13:13.064982

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5ee564514b35'
down_revision: Union[str, Sequence[str], None] = '6cc2b7149752'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'chat_provider_api_keys',
        'last_used_at',
        type_=sa.DateTime(timezone=True),
        postgresql_using='last_used_at AT TIME ZONE \'UTC\'',
        existing_nullable=True,
    )



def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'chat_provider_api_keys',
        'last_used_at',
        type_=sa.DateTime(timezone=False),
        postgresql_using='last_used_at AT TIME ZONE \'UTC\'',
        existing_nullable=True,
    )
