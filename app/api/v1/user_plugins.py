"""
User Plugin Management API Endpoints

Allows users to manage their plugin preferences (enable/disable plugins).
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.models.user import User
from app.services.plugin import (
    ConfigValidationError,
    InternalServerError,
    PluginDisabledError,
    PluginService,
    get_plugin_service,
)

router: APIRouter = APIRouter()


class UserPluginResponse(BaseModel):
    """Response model for user plugin information."""

    plugin_name: str
    enabled: bool
    config: dict[str, Any]
    is_core: bool


class UpdateUserPluginRequest(BaseModel):
    """Request model for updating user plugin state."""

    enabled: bool


class UserPluginConfigRequest(BaseModel):
    """Request model for updating user plugin configuration."""

    config: dict[str, Any]


@router.get("/", response_model=List[UserPluginResponse])
async def list_user_plugins(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> List[UserPluginResponse]:
    """
    List all plugins with their enabled status for the current user.

    Returns information about all available plugins and whether they are
    enabled or disabled for the authenticated user.
    """
    all_plugins = await plugin_service.get_all(session)
    user_plugin_map = await plugin_service.get_user_plugin_map(
        session,
        current_user.id,
    )
    result = []

    for plugin in all_plugins:
        user_plugin = user_plugin_map.get(plugin.name)
        if user_plugin is not None:
            result.append(
                UserPluginResponse(
                    plugin_name=plugin.name,
                    enabled=user_plugin.enabled,
                    config=user_plugin.config or {},
                    is_core=plugin.is_core,
                )
            )
        else:
            result.append(UserPluginResponse(plugin_name=plugin.name, enabled=True, config={}, is_core=plugin.is_core))

    return result


@router.post(
    "/{plugin_name}/configure",
    response_model=UserPluginResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_plugin(
    plugin_name: str,
    user_config: dict[str, Any],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """Create a user plugin with validated configuration."""

    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated.")

    plugin = await plugin_service.get_by_name(session, plugin_name)

    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    if not plugin.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Plugin '{plugin_name}' is not enabled")

    user_plugin = await plugin_service.get_user_plugin(session, current_user.id, plugin.id)
    if user_plugin and len(user_plugin.config) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Plugin '{plugin_name}' is already configured"
        )

    try:
        user_plugin = await plugin_service.create_user_plugin(session, current_user.id, plugin, user_config)
    except ConfigValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except InternalServerError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err

    await session.refresh(plugin)
    return UserPluginResponse(
        plugin_name=plugin.name, enabled=user_plugin.enabled, config=user_plugin.config, is_core=plugin.is_core
    )


@router.get("/{plugin_name}", response_model=UserPluginResponse)
async def get_user_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    plugin = await plugin_service.get_by_name(session, plugin_name)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    user_plugin = await plugin_service.get_user_plugin(session, current_user.id, plugin.id)

    if user_plugin:
        return UserPluginResponse(
            plugin_name=plugin_name,
            enabled=user_plugin.enabled,
            config=user_plugin.config or {},
            is_core=plugin.is_core,
        )
    else:
        return UserPluginResponse(plugin_name=plugin_name, enabled=True, config={}, is_core=plugin.is_core)


@router.patch("/{plugin_name}", response_model=UserPluginResponse)
async def update_user_plugin(
    plugin_name: str,
    request: UpdateUserPluginRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Enable or disable a plugin for the current user.
    """
    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated.")

    plugin = await plugin_service.get_by_name(session, plugin_name)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found.")

    if plugin.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Plugin '{plugin_name}' is not persisted."
        )

    if not plugin.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Plugin '{plugin_name}' is disabled by admin."
        )

    user_plugin = await plugin_service.update_user_plugin_enabled(session, current_user.id, plugin.id, request.enabled)
    return UserPluginResponse(
        plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config, is_core=plugin.is_core
    )


@router.put("/{plugin_name}/config", response_model=UserPluginResponse)
async def update_user_plugin_config(
    plugin_name: str,
    request: UserPluginConfigRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Update configuration for a plugin for the current user.

    This allows users to customize plugin-specific settings.
    """
    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated.")

    plugin = await plugin_service.get_by_name(session, plugin_name)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")

    if not plugin.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Plugin '{plugin_name}' cannot be updated as it is disabled by admin.",
        )

    try:
        user_plugin = await plugin_service.update_user_plugin_config(session, current_user.id, plugin, request.config)
    except PluginDisabledError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    except ConfigValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    await session.refresh(plugin)
    return UserPluginResponse(
        plugin_name=plugin_name, enabled=user_plugin.enabled, config=user_plugin.config, is_core=plugin.is_core
    )


@router.patch("/{plugin_name}/enable", response_model=UserPluginResponse)
async def enable_user_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Enable a plugin for the current user.

    Convenience endpoint for enabling a plugin.
    """
    return await update_user_plugin(
        plugin_name=plugin_name,
        request=UpdateUserPluginRequest(enabled=True),
        current_user=current_user,
        session=session,
        plugin_service=plugin_service,
    )


@router.patch("/{plugin_name}/disable", response_model=UserPluginResponse)
async def disable_user_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Disable a plugin for the current user.

    Convenience endpoint for disabling a plugin.
    """
    return await update_user_plugin(
        plugin_name=plugin_name,
        request=UpdateUserPluginRequest(enabled=False),
        current_user=current_user,
        session=session,
        plugin_service=plugin_service,
    )
