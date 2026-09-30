"""replace username with method in user.logged_in v1 events

Revision ID: 6ccbebfb6a25
Revises: 287f281e6558
Create Date: 2026-09-30 11:34:29.586066

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ccbebfb6a25"
down_revision: Union[str, Sequence[str], None] = "287f281e6558"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only: user.logged_in v1 stored the user's username, a string the user chose,
    # which analytics payloads must not hold. v1 now carries the login method instead, and
    # password login was the only route that emitted, so every stored row becomes
    # {"method": "password"}. The rows are kept, so login_activity_daily (which counts rows)
    # loses no history and needs no refresh. Rows already rewritten are untouched, so this
    # is safe to re-run.
    op.execute(
        """UPDATE raw_events SET payload = '{"method": "password"}'"""
        " WHERE event_type = 'user.logged_in' AND event_version = 1 AND payload->>'method' IS NULL"
    )


def downgrade() -> None:
    # The usernames are gone by design, so there is nothing to restore.
    pass
