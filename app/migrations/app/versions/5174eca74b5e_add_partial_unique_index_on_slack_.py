"""add partial unique indexes on slack_workspaces team_id and user_id

Revision ID: 5174eca74b5e
Revises: 8caaf9fdbce0
Create Date: 2026-06-01 18:27:49.961245

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5174eca74b5e"
down_revision: Union[str, Sequence[str], None] = "8caaf9fdbce0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_slack_workspaces_team_id_active",
        "slack_workspaces",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true AND is_deleted = false"),
        sqlite_where=sa.text("is_active = 1 AND is_deleted = 0"),
    )
    op.create_index(
        "uq_slack_workspaces_user_id_active",
        "slack_workspaces",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true AND is_deleted = false"),
        sqlite_where=sa.text("is_active = 1 AND is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index("uq_slack_workspaces_user_id_active", table_name="slack_workspaces")
    op.drop_index("uq_slack_workspaces_team_id_active", table_name="slack_workspaces")
