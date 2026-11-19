"""The read-side permission engine: resolves which grants satisfy a check.

A user's roles are their own active assignments plus the assignments of any group they actively
belong to, both matched against the same scope chain. It answers whether a permission or role is held
at one scope object, and at which objects of a scope a permission is held. It also answers many
permission checks at once from one read of the user's grants. The write operations (assigning and
revoking roles) never cascade and live elsewhere.
"""

from collections import defaultdict
from collections.abc import Sequence
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import ColumnElement, Subquery, and_, or_
from sqlalchemy.orm import Mapped
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select, SelectOfScalar

from sparkth.core.models.user import User
from sparkth.core.permissions.models import (
    GroupMembership,
    GroupRoleAssignment,
    Role,
    RoleAssignment,
    RolePermission,
)
from sparkth.core.permissions.scopes import ObjectlessPermissionScope, PermissionScope

if TYPE_CHECKING:
    from sparkth.core.permissions import Permission


class PermissionQuestion(NamedTuple):
    """One check: does the user hold ``permission`` at ``scope``?

    ``scope_path`` names the checked object. Without it, an object-bearing scope asks about any of its
    objects and an objectless scope asks about the scope itself.
    """

    permission: "Permission"
    scope: PermissionScope
    scope_path: str | None


def _scope_clause(
    scope_column: Mapped[str],
    object_id_column: Mapped[str | None],
    scope_chain: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """WHERE clause matching an assignment table's (scope, object id) columns against ``scope_chain``,
    the ``(scope name, object id)`` pairs a grant may occupy to satisfy a check.

    The pairs are the checked scope and object, each ancestor object named by the check's scope
    path, and each objectless ancestor.

    Read-side only: a write targets the exact assignment row and must not use this, because writes
    never cascade to ancestor scopes.
    """
    return or_(*(and_(scope_column == name, object_id_column == object_id) for name, object_id in scope_chain))


def _user_role_ids_at_scope(user_id: int | None, scope_chain: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids the user holds via their own active assignments at any of ``scope_chain``."""
    return select(RoleAssignment.role_id).where(
        col(RoleAssignment.user_id) == user_id,
        col(RoleAssignment.is_deleted) == False,
        _scope_clause(col(RoleAssignment.scope), col(RoleAssignment.scope_object_id), scope_chain),
    )


def _active_membership_group_ids(user_id: int | None) -> SelectOfScalar[int]:
    """Subquery of the ids of the groups the user actively belongs to."""
    return select(GroupMembership.group_id).where(
        col(GroupMembership.user_id) == user_id,
        col(GroupMembership.is_deleted) == False,
    )


def _group_role_ids_at_scope(user_id: int | None, scope_chain: list[tuple[str, str | None]]) -> SelectOfScalar[int]:
    """Subquery of role ids granted at any of ``scope_chain`` to a group the user actively belongs to."""
    return select(GroupRoleAssignment.role_id).where(
        col(GroupRoleAssignment.group_id).in_(_active_membership_group_ids(user_id)),
        col(GroupRoleAssignment.is_deleted) == False,
        _scope_clause(col(GroupRoleAssignment.scope), col(GroupRoleAssignment.scope_object_id), scope_chain),
    )


def _granted_role_ids_clause(
    role_id_column: Mapped[int] | Mapped[int | None],
    user_id: int | None,
    scope_chain: list[tuple[str, str | None]],
) -> ColumnElement[bool]:
    """Whether ``role_id_column`` is a role the user holds at any of ``scope_chain`` — via their own
    assignments or via an assignment to a group they actively belong to."""
    return or_(
        role_id_column.in_(_user_role_ids_at_scope(user_id, scope_chain)),
        role_id_column.in_(_group_role_ids_at_scope(user_id, scope_chain)),
    )


async def can(
    user: User,
    permission: "Permission",
    permission_scope: PermissionScope,
    scope_path: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds permission at the given permission scope.

    ``scope_path`` is the materialized path of the checked object; a grant at the object or at any
    ancestor object on the path authorizes. Without it, only the scope itself and its objectless
    ancestors do. Raises ``ValueError`` when the path's leaf names another scope.
    """
    scope_chain = permission_scope.scope_chain(scope_path)
    statement = (
        select(RolePermission.permission)
        .where(
            RolePermission.permission == permission.name,
            _granted_role_ids_clause(col(RolePermission.role_id), user.id, scope_chain),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


async def has_role(
    user: User,
    role_name: str,
    permission_scope: PermissionScope,
    scope_path: str | None,
    session: AsyncSession,
) -> bool:
    """Return whether user holds an active assignment of role_name at the given permission scope.

    ``scope_path`` is the materialized path of the checked object; a role granted at the object or
    at any ancestor object on the path counts. Raises ``ValueError`` when the path's leaf names
    another scope.
    """
    scope_chain = permission_scope.scope_chain(scope_path)
    statement = (
        select(Role.id)
        .where(
            Role.name == role_name,
            _granted_role_ids_clause(col(Role.id), user.id, scope_chain),
        )
        .limit(1)
    )
    result = await session.exec(statement)
    return result.first() is not None


def _reduce_grant_rows(grant_rows: Sequence[tuple[str, str | None]], scope_name: str) -> set[str] | None:
    """Reduce the ``(scope, object id)`` rows of a user's grants to the ids they cover at ``scope_name``.

    A row at an objectless ancestor (NULL object id) covers every object, so it returns ``None``.
    """
    object_ids: set[str] = set()
    for scope, object_id in grant_rows:
        if object_id is None and scope != scope_name:
            return None
        if object_id is not None and scope == scope_name:
            object_ids.add(object_id)
    return object_ids


def _select_grants_with_permissions(
    model: type[RoleAssignment] | type[GroupRoleAssignment],
    owner: ColumnElement[bool],
    permission_names: set[str],
    scope_names: set[str],
) -> Select[tuple[str, str, str | None]]:
    """Select the ``(permission, scope, object id)`` of the active ``model`` rows held by ``owner`` whose role grants
    one of ``permission_names`` at one of ``scope_names``."""
    return (
        select(col(RolePermission.permission), col(model.scope), col(model.scope_object_id))
        .join(RolePermission, col(RolePermission.role_id) == col(model.role_id))
        .where(
            owner,
            col(model.is_deleted) == False,
            col(RolePermission.permission).in_(permission_names),
            col(model.scope).in_(scope_names),
        )
    )


def _select_user_grants(user_id: int | None, permission_names: set[str], scope_names: set[str]) -> Subquery:
    """Subquery of the ``(permission, scope, object id)`` grants the user holds of one of ``permission_names`` at one
    of ``scope_names``, through their own active assignments or those of the groups they actively belong to."""
    own_grants = _select_grants_with_permissions(
        RoleAssignment, col(RoleAssignment.user_id) == user_id, permission_names, scope_names
    )
    group_grants = _select_grants_with_permissions(
        GroupRoleAssignment,
        col(GroupRoleAssignment.group_id).in_(_active_membership_group_ids(user_id)),
        permission_names,
        scope_names,
    )
    return own_grants.union_all(group_grants).subquery()


async def get_accessible_scope_object_ids(
    user: User,
    permission: "Permission",
    permission_scope: PermissionScope,
    session: AsyncSession,
) -> set[str] | None:
    """Return the ids of the ``permission_scope`` objects at which ``user`` holds ``permission``.

    Grants come from the user's own active assignments and from active assignments of the groups
    they actively belong to. Returns ``None`` when a grant at an objectless ancestor (``global``)
    covers every object, otherwise the set of object ids, empty when the user holds the permission
    nowhere. Grants at an object-bearing ancestor are not considered.
    """
    scope_name = permission_scope.name
    scope_names = {name for name, _ in permission_scope.scope_chain(None)}
    grants = _select_user_grants(user.id, {permission.name}, scope_names)
    result = await session.exec(select(grants.c.scope, grants.c.scope_object_id))
    return _reduce_grant_rows(result.all(), scope_name)


def _answer_check(
    grants: set[tuple[str, str | None]], permission_scope: PermissionScope, scope_path: str | None
) -> bool:
    """Whether ``grants``, the ``(scope, object id)`` pairs at which the user holds the checked permission, satisfy a
    check at ``permission_scope``.

    Without ``scope_path``, an object-bearing scope is satisfied by a grant at any of its objects or at an objectless
    ancestor. Otherwise a grant must be on the scope chain of ``scope_path``.
    """
    if scope_path is None and not isinstance(permission_scope, ObjectlessPermissionScope):
        scope_names = {name for name, _ in permission_scope.scope_chain(None)}
        covered = _reduce_grant_rows([grant for grant in grants if grant[0] in scope_names], permission_scope.name)
        return covered is None or bool(covered)
    return not grants.isdisjoint(permission_scope.scope_chain(scope_path))


async def batched_can(user: User, questions: list[PermissionQuestion], session: AsyncSession) -> list[bool]:
    """Return, in order, whether user holds each question's permission at its scope, reading the grants in one query.

    A scope path names one object, and a grant at it or at an ancestor object on the path authorizes. Grants come
    from the user's own active assignments and from active assignments of the groups they actively belong to.
    Raises ``ValueError`` when a path's leaf names another scope.
    """
    if not questions:
        return []
    permission_names = {question.permission.name for question in questions}
    scope_names = {name for question in questions for name, _ in question.scope.scope_chain(question.scope_path)}
    # ponytail: a check on one object fetches every grant of its permission at that scope; narrow the filter to the
    # checked objects if users come to hold thousands of object grants.
    grants = _select_user_grants(user.id, permission_names, scope_names)
    result = await session.exec(select(grants.c.permission, grants.c.scope, grants.c.scope_object_id))
    grants_by_permission: defaultdict[str, set[tuple[str, str | None]]] = defaultdict(set)
    for permission_name, scope, scope_object_id in result.all():
        grants_by_permission[permission_name].add((scope, scope_object_id))
    return [
        _answer_check(grants_by_permission[question.permission.name], question.scope, question.scope_path)
        for question in questions
    ]
