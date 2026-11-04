"""Helpers for the scope objects a permission check or a grant names.

``get_scope_path`` returns the FastAPI dependency that yields the checked object's
scope path for a route: built from a path parameter, a fixed id, an async dependency returning
an id or a scope object record, or ``None`` for an objectless scope. ``convert_to_ints`` converts
the string object ids of grants to the integer ids of the objects they name.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request

from sparkth.core.permissions.scopes import PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

_ScopePathDependency = Callable[..., Awaitable[str | None]]
"""A FastAPI dependency yielding the checked object's scope path, or ``None`` for an objectless scope."""


def build_scope_path(scope: PermissionScope, scope_id: str, parent_path: str | None = None) -> str:
    """Return the materialized path of an object: its parent's path, then ``<scope name>:<scope_id>``.

    Segments are joined by ``/``, root first (``org:5/course:123``); a root-level object has no
    ``parent_path``. A ``scope_id`` containing ``/`` raises ``ValueError``, since it would add
    ancestor segments to the path.
    """
    if "/" in scope_id:
        raise ValueError(f"Scope id {scope_id!r} must not contain '/'")
    segment = f"{scope.name}:{scope_id}"
    return segment if parent_path is None else f"{parent_path}/{segment}"


async def _get_scope_path_of_objectless_scope() -> None:
    """The scope path dependency of an objectless scope: no object, so no path."""
    return None


def _get_scope_path_from_path_param(permission_scope: PermissionScope, scope_param: str) -> _ScopePathDependency:
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


def _get_scope_path_from_fixed_id(permission_scope: PermissionScope, object_id: str) -> _ScopePathDependency:
    """A dependency building the scope path of the fixed ``object_id``."""

    async def resolve_scope_path() -> str:
        return build_scope_path(permission_scope, object_id)

    return resolve_scope_path


def _get_scope_path_from_dependency(
    permission_scope: PermissionScope, object_id: Callable[..., Awaitable[str | ScopeObjectMixin]]
) -> _ScopePathDependency:
    """A dependency building the scope path from what the ``object_id`` dependency returns, an id or a record."""

    async def resolve_scope_path(resolved: str | ScopeObjectMixin = Depends(object_id)) -> str:
        if isinstance(resolved, str):
            return build_scope_path(permission_scope, resolved)
        return resolved.scope_path

    return resolve_scope_path


def get_scope_path(
    permission_scope: PermissionScope,
    scope_param: str | None,
    scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin]] | None,
) -> _ScopePathDependency:
    """Return the dependency that yields a route's scope path, built from the path parameter, the fixed id,
    or the ``object_id`` dependency; an objectless scope has no object and so yields ``None``."""
    if scope_param is not None:
        return _get_scope_path_from_path_param(permission_scope, scope_param)
    if isinstance(scope_object_id, str):
        return _get_scope_path_from_fixed_id(permission_scope, scope_object_id)
    if scope_object_id is not None:
        return _get_scope_path_from_dependency(permission_scope, scope_object_id)
    return _get_scope_path_of_objectless_scope


def convert_to_ints(ids: set[str] | None) -> set[int] | None:
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
