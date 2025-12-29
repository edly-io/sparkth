from typing import Any, Awaitable, Callable, Optional, cast

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from app.core.db import get_session
from app.core.logger import get_logger
from app.models.plugin import Plugin, UserPlugin

logger = get_logger(__name__)


class PluginAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, exclude_paths: Optional[list[str]] = None) -> None:
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
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

        user = getattr(request.state, "user", None)
        if not user:
            response = await call_next(request)
            return response

        has_access = await self._check_plugin_access(user.id, plugin_name)
        if not has_access:
            logger.warning(
                f"User {user.id} attempted to access disabled plugin '{plugin_name}' at path {request.url.path}"
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

    def _get_route_plugin_name(self, request: Request) -> Optional[str]:
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                if hasattr(route, "endpoint"):
                    endpoint = route.endpoint
                    if hasattr(endpoint, "__plugin_name__"):
                        plugin_name = getattr(endpoint, "__plugin_name__")
                        if isinstance(plugin_name, str):
                            return plugin_name
                    if hasattr(route, "tags") and route.tags:
                        for tag in route.tags:
                            if isinstance(tag, str) and tag.startswith("plugin:"):
                                return tag.replace("plugin:", "")
                break
        return None

    async def _check_plugin_access(self, user_id: int, plugin_name: str) -> bool:
        try:
            session = next(get_session())
            return _check_plugin_access(user_id, plugin_name, session, check_system_enabled=True)
        except SQLAlchemyError as e:
            logger.error(f"Database error checking plugin access for user {user_id} and plugin '{plugin_name}': {e}")
            return False


def _check_plugin_access(user_id: int, plugin_name: str, session: Session, check_system_enabled: bool = False) -> bool:
    """
    Shared logic for checking plugin access.

    Args:
        user_id: The user ID to check access for
        plugin_name: The name of the plugin
        session: The database session
        check_system_enabled: If True, also checks if the plugin is enabled at system level

    Returns:
        bool: True if user has access, False otherwise
    """
    plugin_statement = select(Plugin).where(
        Plugin.name == plugin_name,
        Plugin.deleted_at.is_(None),
    )
    plugin = session.exec(plugin_statement).first()

    if plugin is None:
        logger.debug(f"Plugin '{plugin_name}' not found in database. Allowing access by default.")
        return True

    if check_system_enabled and not plugin.enabled:
        logger.debug(f"Plugin '{plugin_name}' is disabled at system level")
        return False

    statement = select(UserPlugin).where(
        UserPlugin.user_id == user_id,
        UserPlugin.plugin_id == plugin.id,
        UserPlugin.deleted_at.is_(None),
    )
    result = session.exec(statement).first()

    if result is None:
        logger.debug(f"No UserPlugin record for user {user_id} and plugin '{plugin_name}'. Allowing access by default.")
        return True

    return result.enabled


def check_user_plugin_access(user_id: int, plugin_name: str, session: Session) -> bool:
    try:
        return _check_plugin_access(user_id, plugin_name, session, check_system_enabled=False)
    except SQLAlchemyError as e:
        logger.error(f"Database error in check_user_plugin_access for user {user_id} and plugin '{plugin_name}': {e}")
        return False


async def get_user_enabled_plugins(user_id: int, session: Session) -> list[str]:
    try:
        statement = (
            select(UserPlugin, Plugin)
            .join(cast(Any, UserPlugin.plugin))
            .where(
                UserPlugin.user_id == user_id,
                UserPlugin.enabled == True,
                UserPlugin.deleted_at.is_(None),
                Plugin.deleted_at.is_(None),
            )
        )
        results = session.exec(statement).all()
        return [plugin.name for _, plugin in results]
    except SQLAlchemyError as e:
        logger.error(f"Database error getting enabled plugins for user {user_id}: {e}")
        return []


async def get_user_disabled_plugins(user_id: int, session: Session) -> list[str]:
    try:
        statement = (
            select(UserPlugin, Plugin)
            .join(cast(Any, UserPlugin.plugin))
            .where(
                UserPlugin.user_id == user_id,
                UserPlugin.enabled == False,
                UserPlugin.deleted_at.is_(None),
                Plugin.deleted_at.is_(None),
            )
        )
        results = session.exec(statement).all()
        return [plugin.name for _, plugin in results]
    except SQLAlchemyError as e:
        logger.error(f"Database error getting disabled plugins for user {user_id}: {e}")
        return []
