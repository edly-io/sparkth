"""create_ragstatus_enum

Revision ID: g6d9f0b1c2d3
Revises: 4d074315201d
Create Date: 2026-04-08 13:51:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g6d9f0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "4d074315201d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ragstatus enum type with uppercase values matching SQLAlchemy enum member names."""
    # Create the enum type with uppercase values
    op.execute("CREATE TYPE ragstatus AS ENUM ('PROCESSING', 'READY', 'FAILED')")

    # Alter the column to use the enum type
    op.execute("ALTER TABLE drive_files ALTER COLUMN rag_status TYPE ragstatus USING rag_status::ragstatus")


def downgrade() -> None:
    """Drop ragstatus enum type."""
    # Revert column to text
    op.execute("ALTER TABLE drive_files ALTER COLUMN rag_status TYPE VARCHAR(50)")

    # Drop the enum type
    op.execute("DROP TYPE ragstatus")
