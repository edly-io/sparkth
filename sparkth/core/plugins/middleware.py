from typing import Any, Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import iter_route_contexts
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.plugins.constants import BEARER_SCHEME
from sparkth.core.routes import get_route_plugin_name
from sparkth.lib.auth import decode_token_username, get_user_by_username
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


def _bearer_token_username(request: Request) -> str | None:
    """Username carried by the request's bearer token, or None when it carries no readable one.

    Reads the header directly rather than through the ``HTTPBearer`` security scheme, which
    is a FastAPI dependency and so only resolves once routing has picked a handler — after
    this middleware has already run.
    """
    header = request.headers.get("authorization")
    if header is None:
        return None

    scheme, _, token = header.partition(" ")
    if scheme.lower() != BEARER_SCHEME or not token:
        return None

    return decode_token_username(token)


class PluginAccessMiddleware(BaseHTTPMiddleware):
    """Reject requests to plugins the caller has turned off, before they reach the route.

    Runs ahead of routing, so it resolves both facts it needs itself: which plugin owns the
    requested URL (from the name ``register_router`` stamps on plugin endpoints) and who is
    asking (from the request's bearer token, via the helpers in ``sparkth.lib.auth`` that
    ``get_current_user`` is built from).

    Anonymous requests fail open. Plugin routers carry unauthenticated endpoints — Slack's
    OAuth callback is called by Slack itself, with no token — and a per-user preference is
    meaningless without a user; endpoints that do require a caller are still rejected by
    their own auth dependency.
    """

    def __init__(self, app: Any, exclude_paths: list[str] | None = None) -> None:
        super().__init__(app)
        # Entries are matched with startswith, so every one of them must be a real path
        # prefix: a bare "/" would exclude every path there is and leave the gate
        # enforcing nothing.
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth",
        ]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if self._is_excluded_path(request.url.path):
            response: Response = await call_next(request)
            return response

        plugin_name = self._get_route_plugin_name(request)
        if not plugin_name:
            response = await call_next(request)
            return response

        username = _bearer_token_username(request)
        if username is None:
            response = await call_next(request)
            return response

        has_access = await self._user_may_use_plugin(username, plugin_name)
        if not has_access:
            logger.warning(
                f"User '{username}' attempted to access disabled plugin '{plugin_name}' at path {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access to plugin '{plugin_name}' is disabled for your account. "
                    f"Please enable the plugin in your settings."
                },
            )

        response = await call_next(request)
        return response

    def _is_excluded_path(self, path: str) -> bool:
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False

    def _get_route_plugin_name(self, request: Request) -> str | None:
        """Name of the plugin owning the route this request targets, or None for a core route.

        Since FastAPI 0.137 include_router() no longer copies the sub-routes into
        app.routes: it appends a single lazy _IncludedRouter branch, which has no .endpoint
        carrying the plugin name. iter_route_contexts flattens those branches into contexts
        that match on the *prefixed* path — the underlying route's own .path is unprefixed
        and would never match the request — while original_route is the real route whose
        endpoint holds the stamp.
        """
        for context in iter_route_contexts(request.app.routes):
            match, _ = context.matches(request.scope)
            if match == Match.FULL:
                return get_route_plugin_name(context.original_route)
        return None

    async def _user_may_use_plugin(self, username: str, plugin_name: str) -> bool:
        """Whether the user this token names still has the plugin enabled.

        A token naming a user that no longer exists passes: there is no preference to
        enforce, and the route's own auth dependency rejects the request anyway. A database
        failure blocks — the gate cannot confirm access, so it must not grant it.
        """
        try:
            async with session_scope() as session:
                user = await get_user_by_username(username, session)
                if user is None or user.id is None:
                    return True
                return await _check_plugin_access_async(user.id, plugin_name, session, check_system_enabled=True)
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Database error checking plugin access for user '{username}' and plugin '{plugin_name}': {e}")
            return False


async def _check_plugin_access_async(
    user_id: int, plugin_name: str, session: AsyncSession, check_system_enabled: bool = False
) -> bool:
    """
    Shared async logic for checking plugin access.

    Args:
        user_id: The user ID to check access for
        plugin_name: The name of the plugin
        session: The async database session
        check_system_enabled: If True, also checks if the plugin is enabled at system level

    Returns:
        bool: True if user has access, False otherwise
    """
    plugin_statement = select(Plugin).where(
        Plugin.name == plugin_name,
        Plugin.deleted_at == None,
    )
    result = await session.exec(plugin_statement)
    plugin = result.one_or_none()

    if plugin is None:
        logger.debug(f"Plugin '{plugin_name}' not found in database. Allowing access by default.")
        return True

    if check_system_enabled and not plugin.enabled:
        logger.debug(f"Plugin '{plugin_name}' is disabled at system level")
        return False

    statement = select(UserPlugin).where(
        UserPlugin.user_id == user_id,
        UserPlugin.plugin_id == plugin.id,
        UserPlugin.deleted_at == None,
    )
    user_plugin_result = await session.exec(statement)
    user_plugin = user_plugin_result.one_or_none()

    if user_plugin is None:
        logger.debug(f"No UserPlugin record for user {user_id} and plugin '{plugin_name}'. Allowing access by default.")
        return True

    return bool(user_plugin.enabled)
