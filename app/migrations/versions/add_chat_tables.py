"""add chat tables

Revision ID: e7f8g9h0i1j2
Revises: 219c976938e7
Create Date: 2026-01-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e7f8g9h0i1j2'
down_revision: Union[str, Sequence[str], None] = '219c976938e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create chat_provider_api_keys table
    op.create_table(
        'chat_provider_api_keys',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('encrypted_key', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_provider_api_keys_is_deleted'), 'chat_provider_api_keys', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_chat_provider_api_keys_user_id'), 'chat_provider_api_keys', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_provider_api_keys_provider'), 'chat_provider_api_keys', ['provider'], unique=False)
    op.create_index('idx_user_provider_active', 'chat_provider_api_keys', ['user_id', 'provider', 'is_active'], unique=False)

    # Create chat_conversations table
    op.create_table(
        'chat_conversations',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.ForeignKeyConstraint(['api_key_id'], ['chat_provider_api_keys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_conversations_is_deleted'), 'chat_conversations', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_chat_conversations_user_id'), 'chat_conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_conversations_api_key_id'), 'chat_conversations', ['api_key_id'], unique=False)
    op.create_index('idx_user_created', 'chat_conversations', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_provider_model', 'chat_conversations', ['provider', 'model'], unique=False)

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP AT TIME ZONE \'UTC\')')),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('model_metadata', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_conversation_id'), 'chat_messages', ['conversation_id'], unique=False)
    op.create_index('idx_conversation_created', 'chat_messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index('idx_conversation_role', 'chat_messages', ['conversation_id', 'role'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop chat_messages table
    op.drop_index('idx_conversation_role', table_name='chat_messages')
    op.drop_index('idx_conversation_created', table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_conversation_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    # Drop chat_conversations table
    op.drop_index('idx_provider_model', table_name='chat_conversations')
    op.drop_index('idx_user_created', table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_api_key_id'), table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_user_id'), table_name='chat_conversations')
    op.drop_index(op.f('ix_chat_conversations_is_deleted'), table_name='chat_conversations')
    op.drop_table('chat_conversations')

    # Drop chat_provider_api_keys table
    op.drop_index('idx_user_provider_active', table_name='chat_provider_api_keys')
    op.drop_index(op.f('ix_chat_provider_api_keys_provider'), table_name='chat_provider_api_keys')
    op.drop_index(op.f('ix_chat_provider_api_keys_user_id'), table_name='chat_provider_api_keys')
    op.drop_index(op.f('ix_chat_provider_api_keys_is_deleted'), table_name='chat_provider_api_keys')
    op.drop_table('chat_provider_api_keys')
