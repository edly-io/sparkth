"""add_slack_plugin_tables

Revision ID: 794bbc28d464
Revises: 2c9970b35fd1, g6d9f0b1c2d3
Create Date: 2026-04-14 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "794bbc28d464"
down_revision: Union[str, Sequence[str], None] = ("2c9970b35fd1", "g6d9f0b1c2d3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "slack_workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.String(length=50), nullable=False),
        sa.Column("team_name", sa.String(length=255), nullable=False),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=False),
        sa.Column("bot_user_id", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slack_workspaces_user_id", "slack_workspaces", ["user_id"])
    op.create_index("ix_slack_workspaces_team_id", "slack_workspaces", ["team_id"])
    op.create_index("ix_slack_workspaces_is_active", "slack_workspaces", ["is_active"])
    op.create_index("ix_slack_workspaces_is_deleted", "slack_workspaces", ["is_deleted"])

    op.create_table(
        "slack_bot_response_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("slack_channel", sa.String(length=50), nullable=False),
        sa.Column("slack_user", sa.String(length=50), nullable=False),
        sa.Column("slack_ts", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("rag_matched", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["slack_workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slack_bot_response_logs_workspace_id", "slack_bot_response_logs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_slack_bot_response_logs_workspace_id", "slack_bot_response_logs")
    op.drop_table("slack_bot_response_logs")

    op.drop_index("ix_slack_workspaces_is_deleted", "slack_workspaces")
    op.drop_index("ix_slack_workspaces_is_active", "slack_workspaces")
    op.drop_index("ix_slack_workspaces_team_id", "slack_workspaces")
    op.drop_index("ix_slack_workspaces_user_id", "slack_workspaces")
    op.drop_table("slack_workspaces")
