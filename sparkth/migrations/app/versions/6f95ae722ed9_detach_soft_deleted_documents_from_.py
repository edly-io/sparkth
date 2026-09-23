"""detach soft-deleted documents from conversations

Clears the attachment rows left behind by every document soft-deleted before the
DOCUMENT_DELETED hook existed. The FK declares ondelete="CASCADE", but a soft delete is
an UPDATE, so the cascade never fired and the join row outlived the document it pointed
at (issue #702).

Without this, those conversations keep counting the deleted file on every turn and
emitting chat.attachment_unusable for it, and `_unusable_status` reports it as a failed
ingestion once its is_deleted branch is gone.

Revision ID: 6f95ae722ed9
Revises: 0a2dfb2685ad
Create Date: 2026-09-23 13:31:58.027023

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6f95ae722ed9"
down_revision: Union[str, Sequence[str], None] = "0a2dfb2685ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Delete attachment rows whose document has been soft-deleted."""
    op.execute(
        sa.text(
            "DELETE FROM chat_conversation_attachments "
            "WHERE document_id IN (SELECT id FROM documents WHERE is_deleted = true)"
        )
    )


def downgrade() -> None:
    """Irreversible.

    The rows carried an ``attached_at`` that is not recorded anywhere else, so there is
    nothing to restore them from. Re-creating them would also re-introduce the bug.
    """
