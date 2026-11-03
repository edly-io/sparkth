"""Where a permission check gets the scope object it checks.

``get_scope_object_source`` returns the FastAPI dependency that yields the checked object's
``(scope_object_id, scope_path)`` for a route: read from a path parameter, a fixed id,
an async dependency returning an id or a scope object record, or nothing for an objectless scope.
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request

from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

_ScopeObjectSource = Callable[..., Awaitable[tuple[str | None, str | None]]]
"""A FastAPI dependency yielding the checked object's ``(scope_object_id, scope_path)``."""


async def _no_object() -> tuple[str | None, str | None]:
    """The object source of an objectless scope: no id and no path."""
    return None, None


def _path_param_source(scope_param: str) -> _ScopeObjectSource:
    """An object source reading the id from the route's ``scope_param`` path parameter."""

    async def source(request: Request) -> tuple[str | None, str | None]:
        if scope_param not in request.path_params:
            logger.error(
                "Permission dependency misconfigured: scope_param %r is not among the route's path params %s",
                scope_param,
                list(request.path_params),
            )
            raise RuntimeError("Permission scope is misconfigured")
        return request.path_params[scope_param], None

    return source


def _fixed_source(object_id: str) -> _ScopeObjectSource:
    """An object source returning the fixed ``object_id``."""

    async def source() -> tuple[str | None, str | None]:
        return object_id, None

    return source


def _dependency_source(object_id: Callable[..., Awaitable[str | ScopeObjectMixin]]) -> _ScopeObjectSource:
    """An object source wrapping the ``object_id`` dependency, which returns an id or a record."""

    async def source(resolved: str | ScopeObjectMixin = Depends(object_id)) -> tuple[str | None, str | None]:
        if isinstance(resolved, str):
            return resolved, None
        return resolved.scope_id, resolved.scope_path

    return source


def get_scope_object_source(
    scope_param: str | None, scope_object_id: str | Callable[..., Awaitable[str | ScopeObjectMixin]] | None
) -> _ScopeObjectSource:
    """Pick the object source for a route: the path parameter, the fixed id, the dependency, or none."""
    if scope_param is not None:
        return _path_param_source(scope_param)
    if isinstance(scope_object_id, str):
        return _fixed_source(scope_object_id)
    if scope_object_id is not None:
        return _dependency_source(scope_object_id)
    return _no_object
