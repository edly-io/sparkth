"""
User Plugin Management API Endpoints

Allows users to manage their plugin preferences (enable/disable plugins).
"""

from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.models.plugin import Plugin, UserPlugin
from app.models.user import User
from app.plugins import get_plugin_manager

router: APIRouter = APIRouter()


def get_or_create_plugin(plugin_name: str, session: Session) -> Plugin:
    """
    Get plugin from database or create if it doesn't exist.

    Args:
        plugin_name: Name of the plugin
        session: Database session

    Returns:
        Plugin instance
    """
    statement = select(Plugin).where(Plugin.name == plugin_name, Plugin.deleted_at == None)
    plugin = session.exec(statement).first()

    if plugin is None:
        plugin = Plugin(name=plugin_name, enabled=True)
        session.add(plugin)
        session.commit()
        session.refresh(plugin)

    return plugin


class UserPluginResponse(BaseModel):
    """Response model for user plugin information."""

    plugin_name: str
    enabled: bool
    config: dict[str, Any]


class UpdateUserPluginRequest(BaseModel):
    """Request model for updating user plugin state."""
    
    enabled: bool


class UserPluginConfigRequest(BaseModel):
    """Request model for updating user plugin configuration."""

    config: dict[str, Any]


@router.get("/", response_model=List[UserPluginResponse])
def list_user_plugins(
    current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> List[UserPluginResponse]:
    """
    List all plugins with their enabled status for the current user.

    Returns information about all available plugins and whether they are
    enabled or disabled for the authenticated user.
    """
    plugin_manager = get_plugin_manager()
    available_plugins = plugin_manager.get_available_plugins()

    statement = (
        select(UserPlugin, Plugin)
        .join(cast(Any, UserPlugin.plugin))
        .where(
            UserPlugin.user_id == current_user.id,
            UserPlugin.deleted_at == None,
        )
    )
    user_plugin_results = session.exec(statement).all()

    user_plugin_map = {plugin.name: user_plugin for user_plugin, plugin in user_plugin_results}

    result: List[UserPluginResponse] = []
    for plugin_name in available_plugins:
        user_plugin = user_plugin_map.get(plugin_name)

        if user_plugin:
            result.append(
                UserPluginResponse(
                    plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {}
                )
            )
        else:
            result.append(UserPluginResponse(plugin_name=plugin_name, enabled=True, config={}))

    return result


@router.get("/{plugin_name}", response_model=UserPluginResponse)
def get_user_plugin(
    plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> UserPluginResponse:
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    plugin_manager = get_plugin_manager()
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    plugin = get_or_create_plugin(plugin_name, session)

    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at == None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})
    else:
        return UserPluginResponse(plugin_name=plugin_name, enabled=True, config={})


@router.patch("/{plugin_name}", response_model=UserPluginResponse)
def update_user_plugin(
    plugin_name: str,
    request: UpdateUserPluginRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserPluginResponse:
    """
    Enable or disable a plugin for the current user.
    """
    plugin_manager = get_plugin_manager()
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    plugin = get_or_create_plugin(plugin_name, session)

    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at == None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        user_plugin.enabled = request.enabled
    else:
        if current_user.id is None or plugin.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User ID or Plugin ID is missing"
            )
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
) -> UserPluginResponse:
    """
    Update configuration for a plugin for the current user.

    This allows users to customize plugin-specific settings.
    """
    plugin_manager = get_plugin_manager()
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    plugin = get_or_create_plugin(plugin_name, session)

    statement = select(UserPlugin).where(
        UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at == None
    )
    user_plugin = session.exec(statement).first()

    if user_plugin:
        user_plugin.config = request.config
    else:
        if current_user.id is None or plugin.id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User ID or Plugin ID is missing"
            )
        user_plugin = UserPlugin(
            user_id=current_user.id,
            plugin_id=plugin.id,
            enabled=True,
            config=request.config,
        )
        session.add(user_plugin)

    session.commit()
    session.refresh(user_plugin)

    return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})


@router.post("/{plugin_name}/enable", response_model=UserPluginResponse)
def enable_user_plugin(
    plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> UserPluginResponse:
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
) -> UserPluginResponse:
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
