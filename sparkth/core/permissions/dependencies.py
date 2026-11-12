"""Helpers for the scope objects a permission check or a grant names.

``build_scope_path_dependency`` returns the FastAPI dependency that yields the checked object's
scope path for a route: built from a path parameter, a fixed id, an async dependency returning
an id or a scope object record, or ``None`` for an objectless scope. ``object_id_str_to_int`` converts
the string object ids of grants to the integer ids of the objects they name.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request

from sparkth.core.permissions.scopes import PermissionScope, build_scope_path
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

_ScopePathDependency = Callable[..., Awaitable[str | None]]
"""A FastAPI dependency yielding the checked object's scope path, or ``None`` for an objectless scope."""


async def _resolve_objectless_scope_path() -> None:
    """The scope path dependency of an objectless scope: no object, so no path."""
    return None


def _build_path_param_dependency(permission_scope: PermissionScope, scope_param: str) -> _ScopePathDependency:
    """A dependency building the scope path from the route's ``scope_param`` path parameter."""

    async def resolve_scope_path(request: Request) -> str:
        if scope_param not in request.path_params:
            logger.error(
                "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                scope_param,
                list(request.path_params),
            )
            raise RuntimeError("Permission scope is misconfigured")
        return build_scope_path(permission_scope, request.path_params[scope_param])

    return resolve_scope_path


def _build_fixed_id_dependency(permission_scope: PermissionScope, object_id: str) -> _ScopePathDependency:
    """A dependency building the scope path of the fixed ``object_id``."""

    async def resolve_scope_path() -> str:
        return build_scope_path(permission_scope, object_id)

    return resolve_scope_path


def _build_object_dependency(
    permission_scope: PermissionScope, object_id: Callable[..., Awaitable[str | ScopeObjectMixin | None]]
) -> _ScopePathDependency:
    """A dependency building the scope path from what the ``object_id`` dependency returns: an id, a record,
    or ``None`` for a missing object, which has no path and so is checked at the scope itself."""

    async def resolve_scope_path(resolved: str | ScopeObjectMixin | None = Depends(object_id)) -> str | None:
        if resolved is None:
            return None
        if isinstance(resolved, str):
            return build_scope_path(permission_scope, resolved)
        return resolved.scope_path

    return resolve_scope_path


def build_scope_path_dependency(
    permission_scope: PermissionScope,
    scope_param: str | None,
    scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin | None]] | None,
) -> _ScopePathDependency:
    """Return the dependency that yields a route's scope path, built from the path parameter, the fixed id,
    or the ``object_id`` dependency; an objectless scope has no object and so yields ``None``."""
    if scope_param is not None:
        return _build_path_param_dependency(permission_scope, scope_param)
    if isinstance(scope_object_id, str):
        return _build_fixed_id_dependency(permission_scope, scope_object_id)
    if scope_object_id is not None:
        return _build_object_dependency(permission_scope, scope_object_id)
    return _resolve_objectless_scope_path


def object_id_str_to_int(ids: set[str] | None) -> set[int] | None:
    """Return the integer ids among ``ids``, the string object ids of scope grants; ``None`` stays ``None``.

    An id that is not a plain integer names no object here, so it is skipped with a warning.
    """
    if ids is None:
        return None
    object_ids: set[int] = set()
    for object_id in ids:
        if object_id.isascii() and object_id.isdigit():
            object_ids.add(int(object_id))
        else:
            logger.warning("Skipped non-numeric scope object id %r", object_id)
    return object_ids
