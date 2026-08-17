from typing import Any, Awaitable, Callable, cast

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import RouteContext, iter_route_contexts
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
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
        # Filled on the first request rather than here: ``app`` is the next ASGI app in the
        # chain, not the FastAPI instance holding the routes, and ``assemble_app`` adds this
        # middleware before it registers the plugin routers anyway. See _flattened_routes.
        self._route_contexts: list[RouteContext] | None = None
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

        user, has_access = await self._resolve_caller_access(username, plugin_name)
        if user is not None:
            # Hand the route the user already loaded here: get_current_user reuses it rather
            # than decoding the same token and re-reading the same row a second time.
            request.state.user = user

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
        for context in self._flattened_routes(request.app):
            match, _ = context.matches(request.scope)
            if match == Match.FULL:
                return get_route_plugin_name(context.original_route)
        return None

    def _flattened_routes(self, app: FastAPI) -> list[RouteContext]:
        """The app's route table, flattened on first use and kept.

        The table is fixed once ``assemble_app`` returns — routes are registered at import
        time, never per request — so flattening it again on every request is repeated work
        on a path every request takes. The matching itself still runs per request: request
        paths carry parameters (``/api/v1/canvas/courses/{course_id}``), so there is no
        path-keyed answer to cache, only the flattened list to match against.

        Args:
            app: The FastAPI instance serving the request, taken from its scope.

        Returns:
            Every route on the app, with nested includes flattened into their own contexts.
        """
        if self._route_contexts is None:
            self._route_contexts = list(iter_route_contexts(app.routes))
        return self._route_contexts

    async def _resolve_caller_access(self, username: str, plugin_name: str) -> tuple[User | None, bool]:
        """The user this token names, and whether they may still use the plugin.

        Both answers come out of one session because the caller needs both and the route
        needs the user again: returning it lets ``get_current_user`` skip a second lookup.

        A token naming a user that no longer exists passes: there is no preference to
        enforce, and the route's own auth dependency rejects the request anyway. A database
        failure blocks — the gate cannot confirm access, so it must not grant it.

        Args:
            username: The username the request's bearer token names.
            plugin_name: The plugin owning the route being requested.

        Returns:
            The user, or None when the token names nobody or the lookup failed, paired with
            whether the request may proceed.
        """
        try:
            async with session_scope() as session:
                user = await get_user_by_username(username, session)
                if user is None or user.id is None:
                    return None, True
                allowed = await _check_plugin_access_async(user.id, plugin_name, session, check_system_enabled=True)
                return user, allowed
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Database error checking plugin access for user '{username}' and plugin '{plugin_name}': {e}")
            return None, False


async def _check_plugin_access_async(
    user_id: int, plugin_name: str, session: AsyncSession, check_system_enabled: bool = False
) -> bool:
    """
    Shared async logic for checking plugin access.

    Reads the system switch and the user's own preference in one query. The join is a
    LEFT OUTER one, and it is keyed on the user as well as the plugin: an inner join would
    hide a plugin nobody has expressed a preference on, and a join keyed on the plugin
    alone would let one user's disabled plugin answer for every other user.

    Both "no plugin row" and "no preference row" mean access is allowed. A plugin the
    registry has never seen is not a disabled plugin, and a user who has never expressed a
    preference has not opted out.

    Args:
        user_id: The user ID to check access for
        plugin_name: The name of the plugin
        session: The async database session
        check_system_enabled: If True, also checks if the plugin is enabled at system level

    Returns:
        bool: True if user has access, False otherwise
    """
    # cast: SQLModel types a column comparison as bool, so the composed ON clause does not
    # satisfy outerjoin's signature without it — the same reason joins elsewhere cast.
    on_clause = cast(
        Any,
        (UserPlugin.plugin_id == Plugin.id) & (UserPlugin.user_id == user_id) & (UserPlugin.deleted_at == None),
    )
    statement = (
        select(Plugin.enabled, UserPlugin.enabled)
        .outerjoin(UserPlugin, on_clause)
        .where(Plugin.name == plugin_name, Plugin.deleted_at == None)
    )
    result = await session.exec(statement)
    row = result.one_or_none()

    if row is None:
        logger.debug(f"Plugin '{plugin_name}' not found in database. Allowing access by default.")
        return True

    system_enabled, user_enabled = row

    if check_system_enabled and not system_enabled:
        logger.debug(f"Plugin '{plugin_name}' is disabled at system level")
        return False

    if user_enabled is None:
        logger.debug(f"No UserPlugin record for user {user_id} and plugin '{plugin_name}'. Allowing access by default.")
        return True

    return bool(user_enabled)
