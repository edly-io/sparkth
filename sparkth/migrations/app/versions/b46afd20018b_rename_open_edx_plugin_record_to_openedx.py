"""rename open-edx plugin record to openedx

Revision ID: b46afd20018b
Revises: 864da1880f41
Create Date: 2026-11-17 12:57:54.294495

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b46afd20018b"
down_revision: Union[str, Sequence[str], None] = "864da1880f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

plugins = sa.table("plugins", sa.column("id", sa.Integer), sa.column("name", sa.String))
user_plugins = sa.table("user_plugins", sa.column("plugin_id", sa.Integer))


def _rename_plugin(old: str, new: str) -> None:
    op.execute(sa.update(plugins).where(plugins.c.name == old).values(name=new))


def upgrade() -> None:
    """Rename the open-edx plugin record to openedx, keeping its id and user rows.

    A server started on the new code before migrating has already created an empty ``openedx``
    record; it is dropped first, so the rename keeps the record users' settings point at.
    """
    old = plugins.alias("old")
    old_exists = sa.exists().where(old.c.name == "open-edx")
    unused = ~sa.exists().where(user_plugins.c.plugin_id == plugins.c.id)
    op.execute(sa.delete(plugins).where(plugins.c.name == "openedx", unused, old_exists))
    _rename_plugin("open-edx", "openedx")


def downgrade() -> None:
    """Restore the open-edx plugin record name."""
    _rename_plugin("openedx", "open-edx")
