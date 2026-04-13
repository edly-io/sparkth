"""add QUEUED to ragstatus enum

Revision ID: i2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-04-13

"""

from alembic import op

revision = "i2b3c4d5e6f7"
down_revision = "h1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ragstatus ADD VALUE IF NOT EXISTS 'QUEUED'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
