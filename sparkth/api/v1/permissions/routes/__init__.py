"""Permissions API router: assignable-permission listing, the self permission-check, and the
mounted sub-routers.

The router is mounted at ``/permissions``. The permission vocabulary is read here (``GET
/permissions``), each permission with what it is for; ``POST /permissions/can/batch`` answers
whether the current user holds each of a list of permissions; role management lives under
``/permissions/roles`` via the role sub-router, group management under ``/permissions/groups`` via
the group sub-router.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.constants import MAX_PERMISSION_CHECKS
from sparkth.api.v1.permissions.routes import groups, roles
from sparkth.api.v1.permissions.schemas import PermissionCheck, PermissionCheckResult, PermissionResponse
from sparkth.core.models.user import User
from sparkth.core.permissions import PERMISSIONS, Permission
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import gettext
from sparkth.lib.permissions import (
    PERMISSION_READ,
    PermissionCheckQuery,
    batched_can,
    get_permission,
    get_permission_scope,
)
from sparkth.lib.permissions.scopes import build_scope_path

router = APIRouter()


def _build_permission_response(permission: Permission) -> PermissionResponse:
    """Describe ``permission`` in the request's language."""
    return PermissionResponse(
        name=permission.name,
        label=gettext(permission.label),
        description=gettext(permission.description),
        category=gettext(permission.category),
        risks=list(permission.risks),
        requires=[required.name for required in permission.requires],
    )


@router.get(
    "",
    response_model=list[PermissionResponse],
    dependencies=[Depends(PERMISSION_READ.require_in_global_scope())],
)
async def list_permissions() -> list[PermissionResponse]:
    """List the permissions a role can hold, each with its label, description, category, risks and the
    permissions it needs, in the request's language."""
    return [_build_permission_response(permission) for permission in PERMISSIONS.iter_values()]


def _get_permission_check_query(check: PermissionCheck) -> PermissionCheckQuery:
    """Resolve a check's permission, then its scope, and build the checked object's scope path when it names one."""
    permission = get_permission(check.permission)
    permission_scope = get_permission_scope(check.scope)
    scope_path = None if check.scope_object_id is None else build_scope_path(permission_scope, check.scope_object_id)
    return PermissionCheckQuery(permission, permission_scope, scope_path)


@router.post("/can/batch", response_model=list[PermissionCheckResult])
async def answer_permission_checks(
    checks: Annotated[list[PermissionCheck], Body(max_length=MAX_PERMISSION_CHECKS)],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[PermissionCheckResult]:
    """Return, in request order, each check with whether the current user holds its permission at its scope.

    A self-check any authenticated user may call about their own grants, for a capped number of
    checks per request. It is not a security boundary (endpoints enforce their own permissions and
    return 403); it lets a client gate UI precisely. Every permission and scope name is resolved against the
    registered vocabulary first: an unknown name rejects the whole request (422) and no check is
    answered.

    - With ``scope_object_id``, an object-bearing scope answers whether the user holds the
      permission at that one object.
    - Without ``scope_object_id`` an object-bearing scope answers whether the user holds the
      permission at any of its objects.
    - An objectless scope answers for the scope itself.
    """
    answers = await batched_can(current_user, [_get_permission_check_query(check) for check in checks], session)
    return [
        PermissionCheckResult(**check.model_dump(), allowed=allowed)
        for check, allowed in zip(checks, answers, strict=True)
    ]


router.include_router(roles.router, prefix="/roles")
router.include_router(groups.router, prefix="/groups")
