"""
User Plugin Management API Endpoints

Allows users to manage their plugin preferences (enable/disable plugins).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.plugins import PluginManager
from pydantic import BaseModel

router = APIRouter()

# Initialize plugin manager to get available plugins
plugin_manager = PluginManager()


def get_or_create_plugin(plugin_name: str, session: Session) -> Plugin:
    """
    Get plugin from database or create if it doesn't exist.

    Args:
        plugin_name: Name of the plugin
        session: Database session

    Returns:
        Plugin instance
    """
    # Try to find existing plugin
    statement = select(Plugin).where(Plugin.name == plugin_name, Plugin.deleted_at is None)
    plugin = session.exec(statement).first()

    if plugin is None:
        # Create new plugin record
        plugin = Plugin(name=plugin_name, enabled=True)
        session.add(plugin)
        session.commit()
        session.refresh(plugin)

    return plugin


class UserPluginResponse(BaseModel):
    """Response model for user plugin information."""

    plugin_name: str
    enabled: bool
    config: dict


class UpdateUserPluginRequest(BaseModel):
    """Request model for updating user plugin state."""

    enabled: bool


class UserPluginConfigRequest(BaseModel):
    """Request model for updating user plugin configuration."""

    config: dict


@router.get("/", response_model=List[UserPluginResponse])
def list_user_plugins(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """
    List all plugins with their enabled status for the current user.

    Returns information about all available plugins and whether they are
    enabled or disabled for the authenticated user.
    """
    # Get all available plugins from the plugin manager
    available_plugins = plugin_manager.get_available_plugins()

    # Get user's plugin settings with join to Plugin table
    statement = (
        select(UserPlugin, Plugin)
        .join(Plugin)
        .where(UserPlugin.user_id == current_user.id, UserPlugin.deleted_at is None)
    )
    user_plugin_results = session.exec(statement).all()

    # Create a mapping of plugin_name to UserPlugin
    user_plugin_map = {plugin.name: user_plugin for user_plugin, plugin in user_plugin_results}

    # Build response
    result = []
    for plugin_name in available_plugins:
        user_plugin = user_plugin_map.get(plugin_name)

        if user_plugin:
            # User has a setting for this plugin
            result.append(
                UserPluginResponse(
                    plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {}
                )
            )
        else:
            # No setting, plugin is enabled by default
            result.append(UserPluginResponse(plugin_name=plugin_name, enabled=True, config={}))

    return result


@router.get("/{plugin_name}", response_model=UserPluginResponse)
def get_user_plugin(
    plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    # Check if plugin exists
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    # Get or create plugin in database
    plugin = get_or_create_plugin(plugin_name, session)

    # Get user's plugin setting
    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at is None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})
    else:
        # No setting, plugin is enabled by default
        return UserPluginResponse(plugin_name=plugin_name, enabled=True, config={})


@router.patch("/{plugin_name}", response_model=UserPluginResponse)
def update_user_plugin(
    plugin_name: str,
    request: UpdateUserPluginRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Enable or disable a plugin for the current user.
    """
    # Check if plugin exists
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    # Get or create plugin in database
    plugin = get_or_create_plugin(plugin_name, session)

    # Check if user already has a setting for this plugin
    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at is None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        # Update existing setting
        user_plugin.enabled = request.enabled
    else:
        # Create new setting
        user_plugin = UserPlugin(user_id=current_user.id, plugin_id=plugin.id, enabled=request.enabled, config={})
        session.add(user_plugin)

    session.commit()
    session.refresh(user_plugin)

    return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})


@router.put("/{plugin_name}/config", response_model=UserPluginResponse)
def update_user_plugin_config(
    plugin_name: str,
    request: UserPluginConfigRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Update configuration for a plugin for the current user.

    This allows users to customize plugin-specific settings.
    """
    # Check if plugin exists
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    # Get or create plugin in database
    plugin = get_or_create_plugin(plugin_name, session)

    # Check if user already has a setting for this plugin
    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at is None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        # Update existing setting
        user_plugin.config = request.config
    else:
        # Create new setting with config
        user_plugin = UserPlugin(
            user_id=current_user.id,
            plugin_id=plugin.id,
            enabled=True,  # Default to enabled
            config=request.config,
        )
        session.add(user_plugin)

    session.commit()
    session.refresh(user_plugin)

    return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})


@router.post("/{plugin_name}/enable", response_model=UserPluginResponse)
def enable_user_plugin(
    plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    """
    Enable a plugin for the current user.

    Convenience endpoint for enabling a plugin.
    """
    return update_user_plugin(
        plugin_name=plugin_name,
        request=UpdateUserPluginRequest(enabled=True),
        current_user=current_user,
        session=session,
    )


@router.post("/{plugin_name}/disable", response_model=UserPluginResponse)
def disable_user_plugin(
    plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    """
    Disable a plugin for the current user.

    Convenience endpoint for disabling a plugin.
    """
    return update_user_plugin(
        plugin_name=plugin_name,
        request=UpdateUserPluginRequest(enabled=False),
        current_user=current_user,
        session=session,
    )
