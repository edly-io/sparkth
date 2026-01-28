"""Add Google Drive tables

Revision ID: b2f4a8c31e72
Revises: a18360344fa7
Create Date: 2026-01-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b2f4a8c31e72'
down_revision: Union[str, Sequence[str], None] = 'a18360344fa7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create drive_oauth_tokens table
    op.create_table('drive_oauth_tokens',
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('access_token_encrypted', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False),
        sa.Column('refresh_token_encrypted', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=False),
        sa.Column('token_expiry', sa.DateTime(), nullable=False),
        sa.Column('scopes', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drive_oauth_tokens_is_deleted'), 'drive_oauth_tokens', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_drive_oauth_tokens_user_id'), 'drive_oauth_tokens', ['user_id'], unique=True)

    # Create drive_folders table
    op.create_table('drive_folders',
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('drive_folder_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('drive_folder_name', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('drive_parent_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('sync_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drive_folders_is_deleted'), 'drive_folders', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_drive_folders_user_id'), 'drive_folders', ['user_id'], unique=False)
    op.create_index(op.f('ix_drive_folders_drive_folder_id'), 'drive_folders', ['drive_folder_id'], unique=False)

    # Create drive_files table
    op.create_table('drive_files',
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('folder_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('drive_file_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('md5_checksum', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('modified_time', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['folder_id'], ['drive_folders.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drive_files_is_deleted'), 'drive_files', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_drive_files_folder_id'), 'drive_files', ['folder_id'], unique=False)
    op.create_index(op.f('ix_drive_files_user_id'), 'drive_files', ['user_id'], unique=False)
    op.create_index(op.f('ix_drive_files_drive_file_id'), 'drive_files', ['drive_file_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_drive_files_drive_file_id'), table_name='drive_files')
    op.drop_index(op.f('ix_drive_files_user_id'), table_name='drive_files')
    op.drop_index(op.f('ix_drive_files_folder_id'), table_name='drive_files')
    op.drop_index(op.f('ix_drive_files_is_deleted'), table_name='drive_files')
    op.drop_table('drive_files')

    op.drop_index(op.f('ix_drive_folders_drive_folder_id'), table_name='drive_folders')
    op.drop_index(op.f('ix_drive_folders_user_id'), table_name='drive_folders')
    op.drop_index(op.f('ix_drive_folders_is_deleted'), table_name='drive_folders')
    op.drop_table('drive_folders')

    op.drop_index(op.f('ix_drive_oauth_tokens_user_id'), table_name='drive_oauth_tokens')
    op.drop_index(op.f('ix_drive_oauth_tokens_is_deleted'), table_name='drive_oauth_tokens')
    op.drop_table('drive_oauth_tokens')
