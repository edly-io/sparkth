"""add unique constraint on drive_folders (user_id, drive_folder_id)

Revision ID: a1b2c3d4e5f6
Revises: 373e6c74ef4d
Create Date: 2026-03-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "373e6c74ef4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_drive_folders_user_folder", "drive_folders", ["user_id", "drive_folder_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_drive_folders_user_folder", "drive_folders", type_="unique")
