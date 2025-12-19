"""
User Plugin Management API Endpoints

Allows users to manage their plugin preferences (enable/disable plugins).
"""

from typing import Any, List, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.models.plugin import Plugin
from app.models.user import User
from app.plugins import get_plugin_manager
from app.services.plugin import ConfigValidationError, PluginService, get_plugin_service

router: APIRouter = APIRouter()


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
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    plugin_service: PluginService = Depends(get_plugin_service),
):
    """
    List all plugins with their enabled status for the current user.

    Returns information about all available plugins and whether they are
    enabled or disabled for the authenticated user.
    """
    all_plugins = plugin_service.get_all(session)
    user_plugin_map = plugin_service.get_user_plugin_map(
        session,
        current_user.id,
    )

    result = []

    for plugin in all_plugins:
        user_plugin = user_plugin_map.get(plugin.name)
        if user_plugin:
            result.append(
                UserPluginResponse(
                    plugin_name=plugin.name,
                    enabled=user_plugin.enabled,
                    config=user_plugin.config or {},
                )
            )
        else:
            result.append(
                UserPluginResponse(
                    plugin_name=plugin.name,
                    enabled=True,
                    config={},
                )
            )

    return result


@router.post(
    "/{plugin_name}/configure",
    response_model=UserPluginResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_plugin(
    plugin_name: str,
    user_config: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    plugin_service: PluginService = Depends(get_plugin_service),
):
    """Create a user plugin with validated configuration."""
    plugin: Plugin = plugin_service.get_by_name(session, plugin_name)

    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    if not plugin.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Plugin '{plugin_name}' is not enabled")

    user_plugin = plugin_service.get_user_plugin(session, current_user.id, plugin.id)
    if user_plugin and user_plugin.config:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Plugin '{plugin_name}' is already configured"
        )

    try:
        user_plugin = plugin_service.create_user_plugin(session, current_user.id, plugin, user_config)
    except ConfigValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return user_plugin


@router.get("/{plugin_name}", response_model=UserPluginResponse)
def get_user_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    plugin_service: PluginService = Depends(get_plugin_service),
):
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    plugin_manager = get_plugin_manager()
    available_plugins = plugin_manager.get_available_plugins()
    if plugin_name not in available_plugins:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    # Get plugin from database
    plugin = plugin_service.get_by_name(session, plugin_name)

    # # Get user's plugin setting
    # statement = select(UserPlugin).where(
    #     UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at.is_(None)
    # )
    user_plugin = plugin_service.get_user_plugin(session, current_user.id, plugin.id)

    if user_plugin:
        return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})
    else:
        return UserPluginResponse(plugin_name=plugin_name, enabled=True, config={})


# @router.patch("/{plugin_name}", response_model=UserPluginResponse)
# def update_user_plugin(
#     plugin_name: str,
#     request: UpdateUserPluginRequest,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ):
#     """
#     Enable or disable a plugin for the current user.
#     """
#     # Check if plugin exists
#     plugin_manager = get_plugin_manager()
#     available_plugins = plugin_manager.get_available_plugins()
#     if plugin_name not in available_plugins:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

#     # Get or create plugin in database
#     plugin = get_or_create_plugin(plugin_name, session)

#     # Check if user already has a setting for this plugin
#     statement = select(UserPlugin).where(
#         UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at.is_(None)
#     )
#     user_plugin = session.exec(statement).first()

#     if user_plugin:
#         # Update existing setting
#         user_plugin.enabled = request.enabled
#     else:
#         # Create new setting
#         user_plugin = UserPlugin(user_id=current_user.id, plugin_id=plugin.id, enabled=request.enabled, config={})
#         session.add(user_plugin)

#     session.commit()
#     session.refresh(user_plugin)

#     return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})


# @router.put("/{plugin_name}/config", response_model=UserPluginResponse)
# def update_user_plugin_config(
#     plugin_name: str,
#     request: UserPluginConfigRequest,
#     current_user: User = Depends(get_current_user),
#     session: Session = Depends(get_session),
# ):
#     """
#     Update configuration for a plugin for the current user.

#     This allows users to customize plugin-specific settings.
#     """
#     # Check if plugin exists
#     plugin_manager = get_plugin_manager()
#     available_plugins = plugin_manager.get_available_plugins()
#     if plugin_name not in available_plugins:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

#     # Get or create plugin in database
#     plugin = get_or_create_plugin(plugin_name, session)

#     # Check if user already has a setting for this plugin
#     statement = select(UserPlugin).where(
#         UserPlugin.user_id == current_user.id, UserPlugin.plugin_id == plugin.id, UserPlugin.deleted_at.is_(None)
#     )
#     user_plugin = session.exec(statement).first()

#     if user_plugin:
#         # Update existing setting
#         user_plugin.config = request.config
#     else:
#         # Create new setting with config
#         user_plugin = UserPlugin(
#             user_id=current_user.id,
#             plugin_id=plugin.id,
#             enabled=True,  # Default to enabled
#             config=request.config,
#         )
#         session.add(user_plugin)

#     session.commit()
#     session.refresh(user_plugin)

#     return UserPluginResponse(plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config or {})


# @router.post("/{plugin_name}/enable", response_model=UserPluginResponse)
# def enable_user_plugin(
#     plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
# ):
#     """
#     Enable a plugin for the current user.

#     Convenience endpoint for enabling a plugin.
#     """
#     return update_user_plugin(
#         plugin_name=plugin_name,
#         request=UpdateUserPluginRequest(enabled=True),
#         current_user=current_user,
#         session=session,
#     )


# @router.post("/{plugin_name}/disable", response_model=UserPluginResponse)
# def disable_user_plugin(
#     plugin_name: str, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)
# ):
#     """
#     Disable a plugin for the current user.

#     Convenience endpoint for disabling a plugin.
#     """
#     return update_user_plugin(
#         plugin_name=plugin_name,
#         request=UpdateUserPluginRequest(enabled=False),
#         current_user=current_user,
#         session=session,
#     )
