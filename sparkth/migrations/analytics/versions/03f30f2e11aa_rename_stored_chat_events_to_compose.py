"""rename stored chat events to compose

Revision ID: 03f30f2e11aa
Revises: 63217cf46808
Create Date: 2026-10-29 16:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "03f30f2e11aa"
down_revision: Union[str, Sequence[str], None] = "63217cf46808"
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
    """Rename every stored ``<old>.<event>`` row to ``<new>.<event>``.

    The continuous aggregate's full-range backfill runs after migrating (``sparkth migrate``).
    """
    raw_events = sa.table("raw_events", sa.column("event_type", sa.String))
    mapping = {f"{old}.{event}": f"{new}.{event}" for event in EVENTS}
    op.execute(
        sa.update(raw_events)
        .where(raw_events.c.event_type.in_(mapping))
        .values(event_type=sa.case(mapping, value=raw_events.c.event_type))
    )


def upgrade() -> None:
    """Rename stored ``chat.*`` events to ``compose.*``."""
    _rename("chat", "compose")


def downgrade() -> None:
    """Rename stored ``compose.*`` events back to ``chat.*``."""
    _rename("compose", "chat")
