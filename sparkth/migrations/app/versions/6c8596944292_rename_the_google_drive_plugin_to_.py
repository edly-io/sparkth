"""rename the google drive plugin to googledrive

Revision ID: 6c8596944292
Revises: d4e8a1b6c3f9
Create Date: 2026-11-17 15:22:43.735247

Renames the plugin's row in ``plugins`` and the ``plugin``-scope role assignments that name it, so every
user keeps their Drive settings and every grant at the plugin's scope keeps working. When the app already
created a ``googledrive`` row, that row is kept and the users' settings move onto it. The downgrade renames
back the same way.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6c8596944292"
down_revision: Union[str, Sequence[str], None] = "d4e8a1b6c3f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import plugin constants.
_HYPHENATED = "google-drive"
_PLAIN = "googledrive"


def _rename_plugin(old: str, new: str) -> None:
    bind = op.get_bind()
    old_id = bind.execute(sa.text("SELECT id FROM plugins WHERE name = :name"), {"name": old}).scalar()
    if old_id is not None:
        new_id = bind.execute(sa.text("SELECT id FROM plugins WHERE name = :name"), {"name": new}).scalar()
        if new_id is None:
            bind.execute(sa.text("UPDATE plugins SET name = :new WHERE id = :id"), {"new": new, "id": old_id})
        else:
            # The new row wins; a user who already has settings on it keeps those.
            ids = {"old_id": old_id, "new_id": new_id}
            bind.execute(
                sa.text(
                    "UPDATE user_plugins SET plugin_id = :new_id WHERE plugin_id = :old_id "
                    "AND user_id NOT IN (SELECT user_id FROM user_plugins WHERE plugin_id = :new_id)"
                ),
                ids,
            )
            bind.execute(sa.text("DELETE FROM user_plugins WHERE plugin_id = :old_id"), ids)
            bind.execute(sa.text("DELETE FROM plugins WHERE id = :old_id"), ids)
    bind.execute(
        sa.text("UPDATE role_assignment SET scope_object_id = :new WHERE scope = 'plugin' AND scope_object_id = :old"),
        {"new": new, "old": old},
    )


def upgrade() -> None:
    _rename_plugin(_HYPHENATED, _PLAIN)


def downgrade() -> None:
    _rename_plugin(_PLAIN, _HYPHENATED)
