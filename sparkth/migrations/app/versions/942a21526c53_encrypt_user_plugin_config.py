"""encrypt user plugin config

Revision ID: 942a21526c53
Revises: b7c6b6b76764
Create Date: 2026-10-21 21:52:59.285907

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from sparkth.core.config import get_settings
from sparkth.core.encryption import get_encryption_service

# revision identifiers, used by Alembic.
revision: str = "942a21526c53"
down_revision: Union[str, Sequence[str], None] = "b7c6b6b76764"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rows() -> list[sa.Row[tuple[int, str | None]]]:
    return list(op.get_bind().execute(sa.text("SELECT id, config FROM user_plugins")).all())


def _write(row_id: int, config: str) -> None:
    op.get_bind().execute(
        sa.text("UPDATE user_plugins SET config = :config WHERE id = :id"), {"config": config, "id": row_id}
    )


def upgrade() -> None:
    """Store every user plugin config encrypted."""
    with op.batch_alter_table("user_plugins") as batch:
        batch.alter_column("config", type_=sa.Text(), postgresql_using="config::text")
    cipher = get_encryption_service(get_settings().ENCRYPTION_KEY)
    for row_id, config in _rows():
        _write(row_id, cipher.encrypt(config or "{}"))


def downgrade() -> None:
    """Store every user plugin config as plain JSON again."""
    cipher = get_encryption_service(get_settings().ENCRYPTION_KEY)
    for row_id, config in _rows():
        _write(row_id, cipher.decrypt(config) if config else "{}")
    with op.batch_alter_table("user_plugins") as batch:
        batch.alter_column("config", type_=sa.JSON(), postgresql_using="config::json")
