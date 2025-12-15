"""
Plugin Access Control Middleware

Enforces user-level plugin access permissions on API routes.
"""

from typing import Callable, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.db import get_session
from app.core.logger import get_logger
from app.models.plugin import UserPlugin

logger = get_logger(__name__)


class PluginAccessMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce plugin-level access control.
    
    This middleware checks if a user has access to plugin routes based on
    their UserPlugin settings. Routes that belong to plugins are tagged
    with plugin metadata, and this middleware validates access before
    allowing the request to proceed.
    """
    
    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        """
        Initialize the middleware.
        
        Args:
            app: FastAPI application instance
            exclude_paths: List of path prefixes to exclude from plugin checks
                          (e.g., ["/api/v1/auth", "/docs", "/openapi.json"])
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
            "/api/v1/auth",  # Auth endpoints should always be accessible
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and check plugin access.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response
        """
        # Check if path should be excluded from plugin checks
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Get plugin name from route metadata
        plugin_name = self._get_route_plugin_name(request)
        
        # If route doesn't belong to a plugin, allow access
        if not plugin_name:
            return await call_next(request)
        
        # Get current user from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        
        # If no user is authenticated, let the auth middleware handle it
        if not user:
            return await call_next(request)
        
        # Check if user has access to this plugin
        has_access = await self._check_plugin_access(user.id, plugin_name)
        
        if not has_access:
            logger.warning(
                f"User {user.id} attempted to access disabled plugin '{plugin_name}' "
                f"at path {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Access to plugin '{plugin_name}' is disabled for your account. "
                             f"Please enable the plugin in your settings."
                }
            )
        
        # User has access, proceed with request
        return await call_next(request)
    
    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if the path should be excluded from plugin checks.
        
        Args:
            path: Request path
            
        Returns:
            True if path should be excluded, False otherwise
        """
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return True
        return False
    
    def _get_route_plugin_name(self, request: Request) -> Optional[str]:
        """
        Extract plugin name from route metadata.
        
        Args:
            request: HTTP request
            
        Returns:
            Plugin name if route belongs to a plugin, None otherwise
        """
        # Try to get plugin name from route metadata
        for route in request.app.routes:
            # Match the route
            match, _ = route.matches(request.scope)
            if match == 2:  # Full match
                # Check if route has plugin metadata
                if hasattr(route, "endpoint"):
                    endpoint = route.endpoint
                    # Check for plugin_name attribute
                    if hasattr(endpoint, "__plugin_name__"):
                        return endpoint.__plugin_name__
                    # Check in route tags
                    if hasattr(route, "tags") and route.tags:
                        for tag in route.tags:
                            # Check if tag indicates a plugin (e.g., "plugin:canvas-plugin")
                            if tag.startswith("plugin:"):
                                return tag.replace("plugin:", "")
                break
        
        return None
    
    async def _check_plugin_access(self, user_id: int, plugin_name: str) -> bool:
        """
        Check if a user has access to a specific plugin.
        
        Args:
            user_id: User ID
            plugin_name: Plugin name
            
        Returns:
            True if user has access, False otherwise
        """
        try:
            # Get database session
            session = next(get_session())
            
            # First, find the plugin by name
            from app.models.plugin import Plugin
            plugin_statement = select(Plugin).where(
                Plugin.name == plugin_name,
                Plugin.deleted_at == None
            )
            plugin = session.exec(plugin_statement).first()
            
            # If plugin doesn't exist in DB, allow access (it may be newly loaded)
            if plugin is None:
                logger.debug(
                    f"Plugin '{plugin_name}' not found in database. Allowing access by default."
                )
                return True
            
            # Check if plugin is enabled at system level
            if not plugin.enabled:
                logger.debug(f"Plugin '{plugin_name}' is disabled at system level")
                return False
            
            # Query UserPlugin table
            statement = select(UserPlugin).where(
                UserPlugin.user_id == user_id,
                UserPlugin.plugin_id == plugin.id,
                UserPlugin.deleted_at == None  # Not soft deleted
            )
            result = session.exec(statement).first()
            
            # If no record exists, plugin is enabled by default for this user
            if result is None:
                logger.debug(
                    f"No UserPlugin record for user {user_id} and plugin '{plugin_name}'. "
                    f"Allowing access by default."
                )
                return True
            
            # Check if plugin is enabled for this user
            return result.enabled
            
        except Exception as e:
            logger.error(
                f"Error checking plugin access for user {user_id} and plugin '{plugin_name}': {e}"
            )
            # On error, deny access to be safe
            return False


def check_user_plugin_access(user_id: int, plugin_name: str, session: Session) -> bool:
    """
    Helper function to check if a user has access to a plugin.
    
    This can be used in route handlers or dependencies to check plugin access.
    
    Args:
        user_id: User ID
        plugin_name: Plugin name
        session: Database session
        
    Returns:
        True if user has access, False otherwise
    """
    try:
        statement = select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.plugin_name == plugin_name,
            UserPlugin.deleted_at.is_(None)
        )
        result = session.exec(statement).first()
        
        # If no record exists, plugin is enabled by default
        if result is None:
            return True
        
        return result.enabled
        
    except Exception as e:
        logger.error(
            f"Error in check_user_plugin_access for user {user_id} "
            f"and plugin '{plugin_name}': {e}"
        )
        return False


async def get_user_enabled_plugins(user_id: int, session: Session) -> list[str]:
    """
    Get list of plugin names that are enabled for a user.
    
    Args:
        user_id: User ID
        session: Database session
        
    Returns:
        List of enabled plugin names
    """
    try:
        # Get all UserPlugin records for this user
        statement = select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.deleted_at.is_(None)
        )
        results = session.exec(statement).all()
        
        # Filter for enabled plugins
        enabled = [record.plugin_name for record in results if record.enabled]
        
        return enabled
        
    except Exception as e:
        logger.error(f"Error getting enabled plugins for user {user_id}: {e}")
        return []


async def get_user_disabled_plugins(user_id: int, session: Session) -> list[str]:
    """
    Get list of plugin names that are disabled for a user.
    
    Args:
        user_id: User ID  
        session: Database session
        
    Returns:
        List of disabled plugin names
    """
    try:
        statement = select(UserPlugin).where(
            UserPlugin.user_id == user_id,
            UserPlugin.enabled == False,
            UserPlugin.deleted_at.is_(None)
        )
        results = session.exec(statement).all()
        
        return [record.plugin_name for record in results]
        
    except Exception as e:
        logger.error(f"Error getting disabled plugins for user {user_id}: {e}")
        return []
