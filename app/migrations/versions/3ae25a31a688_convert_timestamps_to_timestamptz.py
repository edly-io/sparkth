"""convert timestamps to timestamptz

Revision ID: 3ae25a31a688
Revises: a18360344fa7
Create Date: 2026-01-27 14:30:31.586006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '3ae25a31a688'
down_revision: Union[str, Sequence[str], None] = 'a18360344fa7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # plugins
    op.alter_column(
        "plugins",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "plugins",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "plugins",
        "deleted_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
    )

    # user_plugins
    op.alter_column(
        "user_plugins",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_plugins",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user_plugins",
        "deleted_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
    )

    # user
    op.alter_column(
        "user",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "user",
        "deleted_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="deleted_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    # plugins
    op.alter_column(
        "plugins",
        "created_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="created_at",
    )
    op.alter_column(
        "plugins",
        "updated_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="updated_at",
    )
    op.alter_column(
        "plugins",
        "deleted_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="deleted_at",
    )

    # user_plugins
    op.alter_column(
        "user_plugins",
        "created_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="created_at",
    )
    op.alter_column(
        "user_plugins",
        "updated_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="updated_at",
    )
    op.alter_column(
        "user_plugins",
        "deleted_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="deleted_at",
    )

    # user
    op.alter_column(
        "user",
        "created_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="created_at",
    )
    op.alter_column(
        "user",
        "updated_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="updated_at",
    )
    op.alter_column(
        "user",
        "deleted_at",
        type_=sa.DateTime(timezone=False),
        postgresql_using="deleted_at",
    )
