"""make_datetime_columns_timezone_aware

Revision ID: 219c976938e7
Revises: a18360344fa7
Create Date: 2026-01-23 12:09:12.275751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '219c976938e7'
down_revision: Union[str, Sequence[str], None] = 'a18360344fa7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Alter datetime columns in user table to be timezone-aware
    op.alter_column('user', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('user', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('user', 'deleted_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=True)
    
    # Alter datetime columns in plugins table to be timezone-aware
    op.alter_column('plugins', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('plugins', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('plugins', 'deleted_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=True)
    
    # Alter datetime columns in user_plugins table to be timezone-aware
    op.alter_column('user_plugins', 'created_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('user_plugins', 'updated_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=False)
    op.alter_column('user_plugins', 'deleted_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(),
                    nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Revert datetime columns in user_plugins table to be timezone-naive
    op.alter_column('user_plugins', 'deleted_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True)
    op.alter_column('user_plugins', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    op.alter_column('user_plugins', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    
    # Revert datetime columns in plugins table to be timezone-naive
    op.alter_column('plugins', 'deleted_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True)
    op.alter_column('plugins', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    op.alter_column('plugins', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    
    # Revert datetime columns in user table to be timezone-naive
    op.alter_column('user', 'deleted_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=True)
    op.alter_column('user', 'updated_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
    op.alter_column('user', 'created_at',
                    type_=sa.DateTime(),
                    existing_type=sa.DateTime(timezone=True),
                    nullable=False)
