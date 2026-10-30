"""rename chat plugin record to compose

Revision ID: b419b3646c8c
Revises: 02e3fbf6434d
Create Date: 2026-10-29 15:05:27.295198

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b419b3646c8c"
down_revision: Union[str, Sequence[str], None] = "02e3fbf6434d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

plugins = sa.table("plugins", sa.column("name", sa.String))


def _rename_plugin(old: str, new: str) -> None:
    op.execute(sa.update(plugins).where(plugins.c.name == old).values(name=new))


def upgrade() -> None:
    """Rename the chat plugin record to compose, keeping its id and user rows."""
    _rename_plugin("chat", "compose")


def downgrade() -> None:
    """Restore the chat plugin record name."""
    _rename_plugin("compose", "chat")
