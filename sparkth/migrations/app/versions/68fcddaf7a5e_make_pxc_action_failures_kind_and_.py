"""make pxc_action_failures kind and permission enums

Revision ID: 68fcddaf7a5e
Revises: ca6a98634c14
Create Date: 2026-10-15 16:30:52.609659

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "68fcddaf7a5e"
down_revision: Union[str, Sequence[str], None] = "ca6a98634c14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FAILURE_KIND = sa.Enum("rejected", "failed", name="pxcfailurekind")
PREVIEW_PERMISSION = sa.Enum("play", "edit", name="previewpermission")


def upgrade() -> None:
    """Upgrade schema."""
    # A column can take a native enum type only once the type exists, and its strings need a cast.
    FAILURE_KIND.create(op.get_bind(), checkfirst=True)
    PREVIEW_PERMISSION.create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "pxc_action_failures",
        "kind",
        existing_type=sa.VARCHAR(length=16),
        type_=FAILURE_KIND,
        existing_nullable=False,
        postgresql_using="kind::pxcfailurekind",
    )
    op.alter_column(
        "pxc_action_failures",
        "permission",
        existing_type=sa.VARCHAR(length=16),
        type_=PREVIEW_PERMISSION,
        existing_nullable=False,
        postgresql_using="permission::previewpermission",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "pxc_action_failures",
        "permission",
        existing_type=PREVIEW_PERMISSION,
        type_=sa.VARCHAR(length=16),
        existing_nullable=False,
        postgresql_using="permission::text",
    )
    op.alter_column(
        "pxc_action_failures",
        "kind",
        existing_type=FAILURE_KIND,
        type_=sa.VARCHAR(length=16),
        existing_nullable=False,
        postgresql_using="kind::text",
    )
    PREVIEW_PERMISSION.drop(op.get_bind(), checkfirst=True)
    FAILURE_KIND.drop(op.get_bind(), checkfirst=True)
