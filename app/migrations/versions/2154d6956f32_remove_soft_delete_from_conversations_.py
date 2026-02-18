"""Remove soft delete from conversations and add cascade constraints

Revision ID: 2154d6956f32
Revises: b45bf4146679
Create Date: 2026-02-18 13:29:29.141802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2154d6956f32'
down_revision: Union[str, Sequence[str], None] = 'b45bf4146679'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_chat_conversations_is_deleted', table_name='chat_conversations')
    op.drop_column('chat_conversations', 'is_deleted')
    op.drop_column('chat_conversations', 'deleted_at')

    op.drop_constraint(
        'chat_conversations_api_key_id_fkey',
        'chat_conversations',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'chat_conversations_api_key_id_fkey',
        'chat_conversations',
        'chat_provider_api_keys',
        ['api_key_id'],
        ['id'],
        ondelete='SET NULL',
    )

    op.drop_constraint(
        'chat_messages_conversation_id_fkey',
        'chat_messages',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'chat_messages_conversation_id_fkey',
        'chat_messages',
        'chat_conversations',
        ['conversation_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint(
        'chat_messages_conversation_id_fkey',
        'chat_messages',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'chat_messages_conversation_id_fkey',
        'chat_messages',
        'chat_conversations',
        ['conversation_id'],
        ['id'],
    )

    op.drop_constraint(
        'chat_conversations_api_key_id_fkey',
        'chat_conversations',
        type_='foreignkey',
    )
    op.create_foreign_key(
        'chat_conversations_api_key_id_fkey',
        'chat_conversations',
        'chat_provider_api_keys',
        ['api_key_id'],
        ['id'],
    )

    op.add_column(
        'chat_conversations',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'chat_conversations',
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )
    op.create_index(
        'ix_chat_conversations_is_deleted',
        'chat_conversations',
        ['is_deleted'],
    )