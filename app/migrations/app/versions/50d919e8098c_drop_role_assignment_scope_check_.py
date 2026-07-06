"""drop role_assignment scope check constraint

Revision ID: 50d919e8098c
Revises: 9477cf5a43a0
Create Date: 2026-07-06 14:22:46.165620

Drops the ``ck_role_assignment_scope`` CHECK constraint. The (scope, scope_object_id) pairing
it enforced — the global scope names no object, every other scope must — is now enforced in
application code (``assign_role``, via ``PermissionScope.objectless``), so the database no
longer needs to know the scope vocabulary. Alembic's autogenerate does not detect
CHECK-constraint changes, so this body is hand-written rather than generated.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50d919e8098c"
down_revision: Union[str, Sequence[str], None] = "9477cf5a43a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the ck_role_assignment_scope CHECK; the (scope, object_id) pairing is now
    enforced in application code (assign_role). Postgres-targeted — tests build the schema
    from SQLModel.metadata, so this migration does not run under SQLite."""
    op.drop_constraint("ck_role_assignment_scope", "role_assignment", type_="check")


def downgrade() -> None:
    """Recreate the original CHECK (global-only objectless).

    CAVEAT: If any role_assignment rows exist at an objectless non-global scope
    (e.g., scope='whitelist' with scope_object_id=NULL), the constraint recreation
    will fail. Such rows must be deleted before downgrading.
    """
    op.create_check_constraint(
        "ck_role_assignment_scope",
        "role_assignment",
        "(scope = 'global' AND scope_object_id IS NULL) OR (scope != 'global' AND scope_object_id IS NOT NULL)",
    )
