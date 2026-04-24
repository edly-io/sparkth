"""add rbac tables

Revision ID: f1a2b3c4d5e6
Revises: ed5bc53f5b16, e85d903dcb3b
Create Date: 2026-04-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = ("ed5bc53f5b16", "e85d903dcb3b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Create RBAC tables ---
    op.create_table(
        "permission",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permission_name"), "permission", ["name"], unique=True)

    op.create_table(
        "user_role",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role"),
    )
    op.create_index(op.f("ix_user_role_role"), "user_role", ["role"], unique=False)
    op.create_index(op.f("ix_user_role_user_id"), "user_role", ["user_id"], unique=False)

    op.create_table(
        "role_permission",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", "permission_id"),
    )
    op.create_index(op.f("ix_role_permission_permission_id"), "role_permission", ["permission_id"], unique=False)
    op.create_index(op.f("ix_role_permission_role"), "role_permission", ["role"], unique=False)

    # --- Seed default permissions ---
    permissions_table = sa.table(
        "permission",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": 1,
                "name": "users:list",
                "description": "List all users",
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "id": 2,
                "name": "users:read",
                "description": "Read any user profile",
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "id": 3,
                "name": "users:manage",
                "description": "Create, update, and deactivate users",
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "id": 4,
                "name": "users:assign_role",
                "description": "Assign or remove user roles",
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "id": 5,
                "name": "plugins:manage",
                "description": "Enable or disable plugins globally",
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
        ],
    )

    # --- Assign all permissions to admin role ---
    role_permissions_table = sa.table(
        "role_permission",
        sa.column("role", sa.String),
        sa.column("permission_id", sa.Integer),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role": "admin", "permission_id": pid, "created_at": sa.func.now(), "updated_at": sa.func.now()}
            for pid in range(1, 6)
        ],
    )

    # --- Migrate existing users: is_superuser -> user_role ---
    op.execute(
        """
        INSERT INTO user_role (user_id, role, created_at, updated_at)
        SELECT id, 'superuser', NOW(), NOW()
        FROM "user"
        WHERE is_superuser = true
        """
    )
    op.execute(
        """
        INSERT INTO user_role (user_id, role, created_at, updated_at)
        SELECT id, 'member', NOW(), NOW()
        FROM "user"
        WHERE is_superuser = false
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_role_permission_role"), table_name="role_permission")
    op.drop_index(op.f("ix_role_permission_permission_id"), table_name="role_permission")
    op.drop_table("role_permission")
    op.drop_index(op.f("ix_user_role_user_id"), table_name="user_role")
    op.drop_index(op.f("ix_user_role_role"), table_name="user_role")
    op.drop_table("user_role")
    op.drop_index(op.f("ix_permission_name"), table_name="permission")
    op.drop_table("permission")
