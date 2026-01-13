"""Add Google auth fields to user table

Revision ID: d3e5f7a91b84
Revises: b2f4a8c31e72
Create Date: 2026-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd3e5f7a91b84'
down_revision: Union[str, Sequence[str], None] = 'b2f4a8c31e72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add google_id column
    op.add_column('user', sa.Column('google_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f('ix_user_google_id'), 'user', ['google_id'], unique=True)

    # Make hashed_password nullable for Google-only users
    op.alter_column('user', 'hashed_password',
                    existing_type=sqlmodel.sql.sqltypes.AutoString(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Make hashed_password non-nullable again
    op.alter_column('user', 'hashed_password',
                    existing_type=sqlmodel.sql.sqltypes.AutoString(),
                    nullable=False)

    # Remove google_id column
    op.drop_index(op.f('ix_user_google_id'), table_name='user')
    op.drop_column('user', 'google_id')
