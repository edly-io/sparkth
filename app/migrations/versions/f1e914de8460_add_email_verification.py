"""add email verification

Revision ID: f1e914de8460
Revises: e8530a5a5a0e
Create Date: 2026-05-05 00:12:45.536875

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e914de8460"
down_revision: Union[str, Sequence[str], None] = "e8530a5a5a0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_verification_token",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_email_verification_token_user_id"),
        "email_verification_token",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_verification_token_token_hash"),
        "email_verification_token",
        ["token_hash"],
        unique=False,
    )

    # Backfill: mark all existing users as verified.
    # Existing accounts pre-date this feature and should not be locked out.
    user_table = sa.table(
        "user",
        sa.column("email_verified", sa.Boolean()),
        sa.column("email_verified_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        user_table.update().values(
            email_verified=True,
            email_verified_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_email_verification_token_token_hash"),
        table_name="email_verification_token",
    )
    op.drop_index(
        op.f("ix_email_verification_token_user_id"),
        table_name="email_verification_token",
    )
    op.drop_table("email_verification_token")
    op.drop_column("user", "email_verified_at")
    op.drop_column("user", "email_verified")
