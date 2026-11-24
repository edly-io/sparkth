"""Endpoints for the calling user's plugin preferences and the system-wide plugin switch."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.plugins.dependencies import get_usable_plugin_names, require_plugin_manage, require_plugin_use
from sparkth.api.v1.plugins.schemas import PluginConfigRequest, PluginSystemStateResponse, UpdatePluginRequest
from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.core.plugins.service import (
    ConfigValidationError,
    InternalServerError,
    PluginDisabledError,
    PluginResponse,
    PluginService,
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


@router.get("/", response_model=list[PluginResponse])
async def list_plugins(
    usable_plugin_names: set[str] | None = Depends(get_usable_plugin_names),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> list[PluginResponse]:
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
    preference_map = await plugin_service.get_preference_map(session, current_user.id)
    result: list[PluginResponse] = []

    for plugin in all_plugins:
        if usable_plugin_names is not None and plugin.name not in usable_plugin_names:
            continue
        preference = preference_map.get(plugin.name)
        base_config = PluginService.config_with_schema_keys(
            plugin.config_schema, preference.config if preference else None
        )

        safe_config = await PluginService.apply_postprocess(
            plugin.name,
            session,
            current_user.id,
            base_config,
        )

        result.append(
            PluginResponse.for_plugin(
                plugin_name=plugin.name,
                enabled=preference.enabled if preference else True,
                config=safe_config,
                is_core=plugin.is_core,
                config_schema=plugin.config_schema,
            )
        )
    return result


@router.post(
    "/{plugin_name}/configure",
    response_model=PluginResponse,
    dependencies=[Depends(require_plugin_use)],
    status_code=status.HTTP_201_CREATED,
)
async def configure_plugin(
    plugin_name: str,
    user_config: dict[str, Any],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """Save the calling user's first configuration for a plugin, after validating it."""
    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    preference = await plugin_service.get_preference(session, current_user.id, plugin.id)
    if preference and len(preference.config) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_("Plugin '{name}' is already configured").format(name=plugin_name),
        )

    try:
        preprocessed = await PluginService.apply_preprocess(plugin_name, session, current_user.id, user_config)
        validated_config = PluginService.validate_user_config(plugin, preprocessed)
        preference = await plugin_service.create_preference(
            session,
            current_user.id,
            plugin.id,  # type: ignore[arg-type]
            validated_config,
        )
    except (ValueError, ConfigValidationError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except InternalServerError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err

    safe_config = await PluginService.apply_postprocess(plugin_name, session, current_user.id, preference.config)
    return PluginResponse.for_plugin(
        plugin_name=plugin.name,
        enabled=preference.enabled,
        config=safe_config,
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.get("/{plugin_name}", response_model=PluginResponse, dependencies=[Depends(require_plugin_use)])
async def get_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """
    Get the status and configuration of a specific plugin for the current user.
    """
    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)

    preference = await plugin_service.get_preference(session, current_user.id, plugin.id)
    config = PluginService.config_with_schema_keys(plugin.config_schema, preference.config if preference else None)

    if preference:
        safe_config = await PluginService.apply_postprocess(
            plugin_name,
            session,
            current_user.id,  # type: ignore[arg-type]
            config,
        )
        return PluginResponse.for_plugin(
            plugin_name=plugin_name,
            enabled=preference.enabled,
            config=safe_config,
            is_core=plugin.is_core,
            config_schema=plugin.config_schema,
        )
    else:
        return PluginResponse.for_plugin(
            plugin_name=plugin_name,
            enabled=True,
            config=config,
            is_core=plugin.is_core,
            config_schema=plugin.config_schema,
        )


@router.patch("/{plugin_name}", response_model=PluginResponse, dependencies=[Depends(require_plugin_use)])
async def update_plugin(
    plugin_name: str,
    request: UpdatePluginRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """
    Enable or disable a plugin for the current user.
    """
    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    preference = await plugin_service.update_preference_enabled(
        session,
        current_user.id,
        plugin.id,  # type: ignore[arg-type]
        request.enabled,
    )
    return PluginResponse.for_plugin(
        plugin_name=plugin_name,
        enabled=preference.enabled,
        config=PluginService.config_with_schema_keys(plugin.config_schema, preference.config),
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.patch(
    "/{plugin_name}/system", response_model=PluginSystemStateResponse, dependencies=[Depends(require_plugin_manage)]
)
async def update_plugin_system_state(
    plugin_name: str,
    request: UpdatePluginRequest,
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginSystemStateResponse:
    """Switch a plugin on or off for every user, leaving each user's own preference untouched."""
    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    await plugin_service.update_system_enabled(plugin, request.enabled, session)
    await session.commit()
    return PluginSystemStateResponse(plugin_name=plugin.name, system_enabled=plugin.enabled)


@router.put("/{plugin_name}/config", response_model=PluginResponse, dependencies=[Depends(require_plugin_use)])
async def update_plugin_config(
    plugin_name: str,
    request: PluginConfigRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """
    Update configuration for a plugin for the current user.

    This allows users to customize plugin-specific settings.
    """
    if not current_user.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_("User not authenticated."))

    plugin = await get_plugin_or_404(plugin_service, session, plugin_name)
    validate_plugin(plugin)

    try:
        preference = await plugin_service.update_preference_config(session, current_user.id, plugin, request.config)
    except PluginDisabledError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    except (ConfigValidationError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except InternalServerError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err

    await session.commit()
    await session.refresh(plugin)

    await PluginService.apply_cache_sync(plugin_name, session, current_user.id, preference.config)

    safe_config = await PluginService.apply_postprocess(plugin_name, session, current_user.id, preference.config)
    return PluginResponse.for_plugin(
        plugin_name=plugin_name,
        enabled=preference.enabled,
        config=safe_config,
        is_core=plugin.is_core,
        config_schema=plugin.config_schema,
    )


@router.patch("/{plugin_name}/enable", response_model=PluginResponse, dependencies=[Depends(require_plugin_use)])
async def enable_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """
    Enable a plugin for the current user.

    Convenience endpoint for enabling a plugin.
    """
    return await update_plugin(
        plugin_name=plugin_name,
        request=UpdatePluginRequest(enabled=True),
        current_user=current_user,
        session=session,
        plugin_service=plugin_service,
    )


@router.patch("/{plugin_name}/disable", response_model=PluginResponse, dependencies=[Depends(require_plugin_use)])
async def disable_plugin(
    plugin_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    plugin_service: PluginService = Depends(get_plugin_service),
) -> PluginResponse:
    """
    Disable a plugin for the current user.

    Convenience endpoint for disabling a plugin.
    """
    return await update_plugin(
        plugin_name=plugin_name,
        request=UpdatePluginRequest(enabled=False),
        current_user=current_user,
        session=session,
        plugin_service=plugin_service,
    )
