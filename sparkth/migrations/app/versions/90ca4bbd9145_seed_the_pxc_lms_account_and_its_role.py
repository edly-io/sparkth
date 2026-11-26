"""seed the pxc_lms account and its role

Revision ID: 90ca4bbd9145
Revises: 05e3a64e5c3a
Create Date: 2026-11-26 23:14:32.721727

Seeds the built-in ``pxc_lms`` account, which stands for the connected LMS, with no password and an address
under ``.invalid``, so it can neither sign in nor receive mail. It also seeds the built-in ``pxc_lms_user``
role holding ``pxc.activity.play`` and ``pxc.activity.edit``, and assigns that role to the account at
``global``. The upgrade fails if an account already goes by the username.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from uuid6 import uuid7

# revision identifiers, used by Alembic.
revision: str = "90ca4bbd9145"
down_revision: Union[str, Sequence[str], None] = "05e3a64e5c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role symbols.
_USERNAME = "pxc_lms"
_EMAIL = "pxc_lms@sparkth.invalid"
_ROLE = "pxc_lms_user"
_PERMISSIONS = ("pxc.activity.play", "pxc.activity.edit")
_GLOBAL = "global"


def upgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text('SELECT 1 FROM "user" WHERE username = :username'), {"username": _USERNAME}).first():
        raise RuntimeError(f"An account named {_USERNAME!r} already exists; rename it before upgrading.")
    user_id = conn.execute(
        sa.text(
            'INSERT INTO "user" (name, username, email, hashed_password, uuid, email_verified, is_deleted, '
            "created_at, updated_at) "
            "VALUES ('PXC LMS', :username, :email, NULL, :uuid, false, false, now(), now()) RETURNING id"
        ),
        {"username": _USERNAME, "email": _EMAIL, "uuid": uuid7()},
    ).scalar_one()
    role_id = conn.execute(
        sa.text(
            "INSERT INTO role (name, description, is_builtin, created_at, updated_at) "
            "VALUES (:name, 'Held by the pxc_lms account: lets the connected LMS launch PXC activities', "
            "true, now(), now()) RETURNING id"
        ),
        {"name": _ROLE},
    ).scalar_one()
    for permission in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
                "VALUES (:role_id, :permission, now(), now())"
            ),
            {"role_id": role_id, "permission": permission},
        )
    conn.execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope, scope_object_id, is_deleted, created_at, updated_at) "
            "VALUES (:user_id, :role_id, :scope, NULL, false, now(), now())"
        ),
        {"user_id": user_id, "role_id": role_id, "scope": _GLOBAL},
    )


def downgrade() -> None:
    conn = op.get_bind()
    for table in ("role_assignment", "group_role_assignment", "role_permission"):
        conn.execute(
            sa.text(f"DELETE FROM {table} WHERE role_id IN (SELECT id FROM role WHERE name = :name)"),
            {"name": _ROLE},
        )
    conn.execute(sa.text("DELETE FROM role WHERE name = :name"), {"name": _ROLE})
    conn.execute(
        sa.text('DELETE FROM role_assignment WHERE user_id IN (SELECT id FROM "user" WHERE username = :username)'),
        {"username": _USERNAME},
    )
    conn.execute(sa.text('DELETE FROM "user" WHERE username = :username'), {"username": _USERNAME})
