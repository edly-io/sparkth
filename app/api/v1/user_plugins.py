"""
User Plugin Management API Endpoints

Allows users to manage their plugin preferences (enable/disable plugins).
"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.models.plugin import Plugin
from app.models.user import User
from app.services.plugin import (
    ConfigValidationError,
    PluginDisabledError,
    PluginService,
    UserPluginResponse,
    get_plugin_service,
)
from app.services.plugin_adapters.registry import PLUGIN_CONFIG_ADAPTERS

# Get the root logger
logger = logging.getLogger()


router: APIRouter = APIRouter()


class UpdateUserPluginRequest(BaseModel):
    """Request model for updating user plugin state."""

    enabled: bool


class UserPluginConfigRequest(BaseModel):
    """Request model for updating user plugin configuration."""

    config: dict[str, Any]


async def get_plugin_or_404(session: AsyncSession, plugin_service: PluginService, plugin_name: str):
    plugin = await plugin_service.get_by_name(session, plugin_name)
    if not plugin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Plugin '{plugin_name}' not found")
    return plugin


async def check_plugin_enabled(plugin: Plugin):
    if not plugin.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Plugin '{plugin.name}' is disabled by admin."
        )


async def apply_adapter_preprocess(plugin_name: str, user_id: int, config: dict, session: AsyncSession) -> dict:
    adapter = PLUGIN_CONFIG_ADAPTERS.get(plugin_name)
    if adapter:
        return await adapter.preprocess_config(session=session, user_id=user_id, incoming_config=config)
    return config


async def apply_adapter_postprocess(plugin_name: str, user_id: int, config: dict, session: AsyncSession) -> dict:
    adapter = PLUGIN_CONFIG_ADAPTERS.get(plugin_name)
    if adapter:
        return await adapter.postprocess_config(session=session, user_id=user_id, stored_config=config)
    return config


@router.get("/", response_model=List[UserPluginResponse])
async def list_user_plugins(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> List[UserPluginResponse]:
    all_plugins = await plugin_service.get_all(session)
    user_plugin_map = await plugin_service.get_user_plugin_map(session, current_user.id)
    result: list[UserPluginResponse] = []

    for plugin in all_plugins:
        user_plugin = user_plugin_map.get(plugin.name)
        config_keys = PluginService.initial_config(plugin.config_schema)

        if user_plugin:
            config = await apply_adapter_postprocess(plugin.name, current_user.id, user_plugin.config, session)
            result.append(
                UserPluginResponse(
                    plugin_name=plugin.name, enabled=user_plugin.enabled, config=config, is_core=plugin.is_core
                )
            )
        else:
            config = await apply_adapter_postprocess(plugin.name, current_user.id, config_keys, session)
            result.append(
                UserPluginResponse(plugin_name=plugin.name, enabled=True, config=config, is_core=plugin.is_core)
            )
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
        processed_config = await apply_adapter_preprocess(plugin_name, current_user.id, user_config, session)
        validated_config = PluginService.validate_user_config(plugin, processed_config)
    except ConfigValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    user_plugin = await plugin_service.create_user_plugin(session, current_user.id, plugin, validated_config)
    response_config = await apply_adapter_postprocess(plugin_name, current_user.id, user_plugin.config, session)

    return UserPluginResponse(
        plugin_name=plugin.name, enabled=user_plugin.enabled, config=response_config, is_core=plugin.is_core
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
    config_keys = PluginService.initial_config(plugin.config_schema)

    if user_plugin:
        return UserPluginResponse(
            plugin_name=plugin_name,
            enabled=user_plugin.enabled,
            config=user_plugin.config or config_keys,
            is_core=plugin.is_core,
        )
    else:
        return UserPluginResponse(plugin_name=plugin_name, enabled=True, config=config_keys, is_core=plugin.is_core)


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
        processed_config = await apply_adapter_preprocess(plugin_name, current_user.id, request.config, session)
        user_plugin = await plugin_service.update_user_plugin_config(session, current_user.id, plugin, processed_config)
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
