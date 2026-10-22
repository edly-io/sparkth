"""cascade pxc action failures with their activity

Revision ID: 51c82933dce3
Revises: 72c7ac343c02
Create Date: 2026-10-19 17:04:55.492346

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51c82933dce3"
down_revision: Union[str, Sequence[str], None] = "72c7ac343c02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "pxc_action_failures_activity_id_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(FK_NAME, "pxc_action_failures", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "pxc_action_failures", "pxc_activities", ["activity_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK_NAME, "pxc_action_failures", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "pxc_action_failures", "pxc_activities", ["activity_id"], ["id"])
