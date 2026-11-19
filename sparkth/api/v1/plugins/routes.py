"""User plugin preference endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.plugins.dependencies import get_usable_plugin_names, require_plugin_use
from sparkth.api.v1.plugins.schemas import UpdateUserPluginRequest, UserPluginConfigRequest
from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.core.plugins.service import (
    ConfigValidationError,
    InternalServerError,
    PluginDisabledError,
    PluginService,
    UserPluginResponse,
    get_plugin_service,
)
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _

router: APIRouter = APIRouter()


async def get_plugin_or_404(plugin_service: PluginService, session: AsyncSession, name: str) -> Plugin:
    plugin = await plugin_service.get_by_name(session, name)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_("Plugin '{name}' not found").format(name=name)
        )
    return plugin


def validate_plugin(plugin: Plugin) -> None:
    if not plugin.id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plugin '{plugin.name}' is not persisted.",  # i18n-exempt: internal invariant
        )
    if not plugin.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_("Plugin '{name}' is not enabled").format(name=plugin.name)
        )


@router.get("/", response_model=list[UserPluginResponse])
async def list_user_plugins(
    usable_plugin_names: set[str] | None = Depends(get_usable_plugin_names),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> list[UserPluginResponse]:
    """
    List the plugins the current user may use, with their enabled status.

    Returns each usable plugin and whether it is enabled or disabled,
    and pre-populates the config with keys from the plugin's schema.
    """
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user has no ID.",  # i18n-exempt: internal invariant
        )

    all_plugins = await plugin_service.get_all(session)
    user_plugin_map = await plugin_service.get_user_plugin_map(session, current_user.id)
    result: list[UserPluginResponse] = []

    for plugin in all_plugins:
        if usable_plugin_names is not None and plugin.name not in usable_plugin_names:
            continue
        user_plugin = user_plugin_map.get(plugin.name)
        base_config = PluginService.config_with_schema_keys(
            plugin.config_schema, user_plugin.config if user_plugin else None
        )

        safe_config = await PluginService.apply_postprocess(
            plugin.name,
            session,
            current_user.id,
            base_config,
        )

        result.append(
            UserPluginResponse.for_plugin(
                plugin_name=plugin.name,
                enabled=user_plugin.enabled if user_plugin else True,
                config=safe_config,
                is_core=plugin.is_core,
                config_schema=plugin.config_schema,
            )
        )
    return result


@router.post(
    "/{plugin_name}/configure",
    response_model=UserPluginResponse,
    dependencies=[Depends(require_plugin_use)],
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    user_plugin = await plugin_service.get_user_plugin(session, current_user.id, plugin.id)
    if user_plugin and len(user_plugin.config) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_("Plugin '{name}' is already configured").format(name=plugin_name),
        )

    try:
        preprocessed = await PluginService.apply_preprocess(plugin_name, session, current_user.id, user_config)
        validated_config = PluginService.validate_user_config(plugin, preprocessed)
        user_plugin = await plugin_service.create_user_plugin(
            session,
            current_user.id,
            plugin.id,  # type: ignore[arg-type]
            validated_config,
        )
    except (ValueError, ConfigValidationError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except InternalServerError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err

    safe_config = await PluginService.apply_postprocess(plugin_name, session, current_user.id, user_plugin.config)
    return UserPluginResponse.for_plugin(
        plugin_name=plugin.name,
        enabled=user_plugin.enabled,
        config=safe_config,
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.get("/{plugin_name}", response_model=UserPluginResponse, dependencies=[Depends(require_plugin_use)])
async def get_user_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> UserPluginResponse:
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)

    user_plugin = await plugin_service.get_user_plugin(session, current_user.id, plugin.id)
    config = PluginService.config_with_schema_keys(plugin.config_schema, user_plugin.config if user_plugin else None)

    if user_plugin:
        safe_config = await PluginService.apply_postprocess(
            plugin_name,
            session,
            current_user.id,  # type: ignore[arg-type]
            config,
        )
        return UserPluginResponse.for_plugin(
            plugin_name=plugin_name,
            enabled=user_plugin.enabled,
            config=safe_config,
            is_core=plugin.is_core,
            config_schema=plugin.config_schema,
        )
    else:
        return UserPluginResponse.for_plugin(
            plugin_name=plugin_name,
            enabled=True,
            config=config,
            is_core=plugin.is_core,
            config_schema=plugin.config_schema,
        )


@router.patch("/{plugin_name}", response_model=UserPluginResponse, dependencies=[Depends(require_plugin_use)])
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    user_plugin = await plugin_service.update_user_plugin_enabled(
        session,
        current_user.id,
        plugin.id,  # type: ignore[arg-type]
        request.enabled,
    )
    return UserPluginResponse.for_plugin(
        plugin_name=plugin_name,
        enabled=user_plugin.enabled,
        config=PluginService.config_with_schema_keys(plugin.config_schema, user_plugin.config),
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.put("/{plugin_name}/config", response_model=UserPluginResponse, dependencies=[Depends(require_plugin_use)])
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    try:
        user_plugin = await plugin_service.update_user_plugin_config(session, current_user.id, plugin, request.config)
    except PluginDisabledError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    except (ConfigValidationError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except InternalServerError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err

    await session.commit()
    await session.refresh(plugin)

    await PluginService.apply_cache_sync(plugin_name, session, current_user.id, user_plugin.config)

    safe_config = await PluginService.apply_postprocess(plugin_name, session, current_user.id, user_plugin.config)
    return UserPluginResponse.for_plugin(
        plugin_name=plugin_name,
        enabled=user_plugin.enabled,
        config=safe_config,
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.patch("/{plugin_name}/enable", response_model=UserPluginResponse, dependencies=[Depends(require_plugin_use)])
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


@router.patch("/{plugin_name}/disable", response_model=UserPluginResponse, dependencies=[Depends(require_plugin_use)])
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
