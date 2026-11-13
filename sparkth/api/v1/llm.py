"""REST endpoints for LLMConfig management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.llm import LLMConfig
from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.i18n import _
from sparkth.lib.llm import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LLMConfigCreate,
    LLMConfigDuplicateNameError,
    LLMConfigListResponse,
    LLMConfigNotFoundError,
    LLMConfigResponse,
    LLMConfigRotateKey,
    LLMConfigService,
    LLMConfigSetActive,
    LLMConfigUpdate,
    LLMConfigValidationError,
    ProviderCatalogResponse,
    ProviderInfo,
    get_llm_service,
    get_provider_catalog,
)
from sparkth.lib.log import get_logger
from sparkth.lib.permissions import (
    LLM_CONFIG_CREATE,
    LLM_CONFIG_DELETE,
    LLM_CONFIG_READ,
    LLM_CONFIG_UPDATE,
    get_listed_owner_id,
    get_own_user_scope_id,
)
from sparkth.lib.permissions.scopes import USER

logger = get_logger(__name__)
router = APIRouter()


@router.get("/providers", response_model=ProviderCatalogResponse)
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> ProviderCatalogResponse:
    """Return the catalog of supported LLM providers and their available models."""
    return ProviderCatalogResponse(
        providers=[ProviderInfo(id=p["id"], label=p["label"], models=p["models"]) for p in get_provider_catalog()],
        default_provider=DEFAULT_PROVIDER,
        default_model=DEFAULT_MODEL,
    )


async def get_llm_config(config_id: int, session: AsyncSession = Depends(get_async_session)) -> LLMConfig:
    """Resolve a config id to its non-deleted record, whoever owns it. Raises 404 when there is none."""
    result = await session.exec(
        select(LLMConfig).where(LLMConfig.id == config_id, col(LLMConfig.is_deleted) == False)  # noqa: E712
    )
    config = result.first()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("LLM config not found"))
    return config


async def get_llm_config_owner_id(config: LLMConfig = Depends(get_llm_config)) -> str:
    """Return the id of the user who owns the config, as the object id of its ``user`` scope."""
    return str(config.user_id)


def _to_response(config: LLMConfig) -> LLMConfigResponse:
    return LLMConfigResponse.model_validate(config)


@router.post(
    "/configs",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(LLM_CONFIG_CREATE.require_for_object(USER, get_own_user_scope_id))],
)
async def create_llm_config(
    body: LLMConfigCreate,
    owner_id: str = Depends(get_own_user_scope_id),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        config = await service.create(
            session=session,
            user_id=int(owner_id),
            name=body.name,
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
        )
        await session.commit()
        return _to_response(config)
    except LLMConfigDuplicateNameError as exc:
        logger.warning("LLMConfig name conflict for user %s: %s", owner_id, exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/configs",
    response_model=LLMConfigListResponse,
    dependencies=[Depends(LLM_CONFIG_READ.require_for_object(USER, get_listed_owner_id))],
)
async def list_llm_configs(
    include_inactive: bool = Query(default=False),
    owner_id: str = Depends(get_listed_owner_id),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigListResponse:
    configs = await service.list(session=session, user_id=int(owner_id), include_inactive=include_inactive)
    return LLMConfigListResponse(
        configs=[_to_response(c) for c in configs],
        total=len(configs),
    )


@router.patch(
    "/configs/{config_id}",
    response_model=LLMConfigResponse,
    dependencies=[Depends(LLM_CONFIG_UPDATE.require_for_object(USER, get_llm_config_owner_id))],
)
async def update_llm_config(
    config_id: int,
    body: LLMConfigUpdate,
    config: LLMConfig = Depends(get_llm_config),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    if not body.name and not body.model:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_("Empty body. Nothing to update.")
        )

    try:
        updated = await service.update(
            session=session,
            user_id=config.user_id,
            config_id=config_id,
            name=body.name,
            model=body.model,
        )
        await session.commit()
        return _to_response(updated)
    except LLMConfigDuplicateNameError as exc:
        logger.warning("LLMConfig name conflict updating config %s for user %s: %s", config_id, config.user_id, exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LLMConfigValidationError as exc:
        logger.warning("Validation error updating LLMConfig %s: %s", config_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for user %s: %s", config_id, config.user_id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put(
    "/configs/{config_id}/key",
    response_model=LLMConfigResponse,
    dependencies=[Depends(LLM_CONFIG_UPDATE.require_for_object(USER, get_llm_config_owner_id))],
)
async def rotate_llm_config_key(
    config_id: int,
    body: LLMConfigRotateKey,
    config: LLMConfig = Depends(get_llm_config),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        updated = await service.rotate_key(
            session=session,
            user_id=config.user_id,
            config_id=config_id,
            api_key=body.api_key,
        )
        await session.commit()
        return _to_response(updated)
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for key rotation (user %s): %s", config_id, config.user_id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/configs/{config_id}/active",
    response_model=LLMConfigResponse,
    dependencies=[Depends(LLM_CONFIG_UPDATE.require_for_object(USER, get_llm_config_owner_id))],
)
async def set_llm_config_active(
    config_id: int,
    body: LLMConfigSetActive,
    config: LLMConfig = Depends(get_llm_config),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        updated = await service.set_active(
            session=session,
            user_id=config.user_id,
            config_id=config_id,
            is_active=body.is_active,
        )
        await session.commit()
        return _to_response(updated)
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for active state update (user %s): %s", config_id, config.user_id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(LLM_CONFIG_DELETE.require_for_object(USER, get_llm_config_owner_id))],
)
async def delete_llm_config(
    config_id: int,
    config: LLMConfig = Depends(get_llm_config),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> None:
    deleted = await service.delete(
        session=session,
        user_id=config.user_id,
        config_id=config_id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_("LLM config not found"))
    await session.commit()
