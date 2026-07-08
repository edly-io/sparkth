"""drop is_superuser column

Revision ID: 3364c02e8569
Revises: b8bf876007e2
Create Date: 2026-06-18 17:39:30.811152

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3364c02e8569"
down_revision: Union[str, Sequence[str], None] = "b8bf876007e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user", "is_superuser")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
