"""strip legacy chat plugin config fields from user_plugins

Revision ID: 74afa7d018c0
Revises: 7f8a52663a6b
Create Date: 2026-05-08 12:04:46.674966

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '74afa7d018c0'
down_revision: Union[str, Sequence[str], None] = '7f8a52663a6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL-only: uses JSONB operators not available in SQLite.
    # CI runs against SQLite so this path is skipped there; production runs PostgreSQL.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        UPDATE user_plugins
        SET config = (
            config::jsonb
            - '{provider,model,provider_api_key_ref,llm_config_name,llm_provider,llm_model}'::text[]
        )::json
        WHERE config::jsonb ?| ARRAY['provider', 'model', 'provider_api_key_ref',
                                     'llm_config_name', 'llm_provider', 'llm_model']
        """
    )


def downgrade() -> None:
    # Irreversible data migration: stripped field values are not recoverable.
    pass
