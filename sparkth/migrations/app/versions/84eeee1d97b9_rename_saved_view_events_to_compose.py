"""rename saved view events to compose

Revision ID: 84eeee1d97b9
Revises: b419b3646c8c
Create Date: 2026-10-29 16:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84eeee1d97b9"
down_revision: Union[str, Sequence[str], None] = "b419b3646c8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENTS = (
    "conversation_started",
    "message_sent",
    "completion_served",
    "tool_invoked",
    "document_attached",
    "document_detached",
    "documents_skipped",
    "attachment_unusable",
    "scope_classified",
    "rag_search_classified",
    "rag_search_completed",
    "turn_failed",
)


def _rename(old: str, new: str) -> None:
    """Rewrite ``config["event"]`` of saved Explore views from ``<old>.<event>`` to ``<new>.<event>``."""
    views = sa.table("analytics_view", sa.column("id", sa.Uuid), sa.column("config", sa.JSON))
    names = {f"{old}.{event}": f"{new}.{event}" for event in EVENTS}
    conn = op.get_bind()
    for view_id, config in conn.execute(sa.select(views.c.id, views.c.config)).all():
        if config.get("event") in names:
            conn.execute(
                sa.update(views).where(views.c.id == view_id).values(config={**config, "event": names[config["event"]]})
            )


def upgrade() -> None:
    """Rename saved view events from ``chat.*`` to ``compose.*``."""
    _rename("chat", "compose")


def downgrade() -> None:
    """Rename saved view events from ``compose.*`` back to ``chat.*``."""
    _rename("compose", "chat")
