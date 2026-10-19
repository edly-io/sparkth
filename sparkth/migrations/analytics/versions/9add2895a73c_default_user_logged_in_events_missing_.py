"""default user.logged_in events missing method to password

Revision ID: 9add2895a73c
Revises: 3b6c4d3ec24f
Create Date: 2026-10-19 15:54:32.496686

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9add2895a73c"
down_revision: Union[str, Sequence[str], None] = "3b6c4d3ec24f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only, repeating 6ccbebfb6a25 for username-carrying v1 rows an older app instance
    # wrote after it ran. Password login was the only route that emitted them. The migrate
    # command's backfill refreshes login_activity_daily_by_method afterwards.
    op.execute(
        """UPDATE raw_events SET payload = '{"method": "password"}'"""
        " WHERE event_type = 'user.logged_in' AND event_version = 1 AND payload->>'method' IS NULL"
    )


def downgrade() -> None:
    # The usernames are gone by design, so there is nothing to restore.
    pass
