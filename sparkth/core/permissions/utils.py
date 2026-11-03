"""Where a permission check gets the scope path it checks.

``get_scope_path`` returns the FastAPI dependency that yields the checked object's
scope path for a route: built from a path parameter, a fixed id, an async dependency returning
an id or a scope object record, or ``None`` for an objectless scope.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request

from sparkth.core.permissions.scopes import PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin, build_scope_path
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

_ScopeObjectSource = Callable[..., Awaitable[str | None]]
"""A FastAPI dependency yielding the checked object's scope path, or ``None`` for an objectless scope."""


async def _no_object() -> None:
    """The object source of an objectless scope: no object, so no path."""
    return None


def _path_param_source(permission_scope: PermissionScope, scope_param: str) -> _ScopeObjectSource:
    """An object source building the scope path from the route's ``scope_param`` path parameter."""

    async def source(request: Request) -> str:
        if scope_param not in request.path_params:
            logger.error(
                "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                scope_param,
                list(request.path_params),
            )
            raise RuntimeError("Permission scope is misconfigured")
        return build_scope_path(permission_scope, request.path_params[scope_param])

    return source


def _fixed_source(permission_scope: PermissionScope, object_id: str) -> _ScopeObjectSource:
    """An object source building the scope path of the fixed ``object_id``."""

    async def source() -> str:
        return build_scope_path(permission_scope, object_id)

    return source


def _dependency_source(
    permission_scope: PermissionScope, object_id: Callable[..., Awaitable[str | ScopeObjectMixin]]
) -> _ScopeObjectSource:
    """An object source wrapping the ``object_id`` dependency, which returns an id or a record."""

    async def source(resolved: str | ScopeObjectMixin = Depends(object_id)) -> str:
        if isinstance(resolved, str):
            return build_scope_path(permission_scope, resolved)
        return resolved.scope_path

    return source


def get_scope_path(
    permission_scope: PermissionScope,
    scope_param: str | None,
    scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin]] | None,
) -> _ScopeObjectSource:
    """Pick the scope path source for a route: the path parameter, the fixed id, the dependency, or none."""
    if scope_param is not None:
        return _path_param_source(permission_scope, scope_param)
    if isinstance(scope_object_id, str):
        return _fixed_source(permission_scope, scope_object_id)
    if scope_object_id is not None:
        return _dependency_source(permission_scope, scope_object_id)
    return _no_object
