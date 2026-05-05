"""REST endpoints for LLMConfig management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.core.logger import get_logger
from app.llm.exceptions import LLMConfigDuplicateNameError, LLMConfigNotFoundError, LLMConfigValidationError
from app.llm.schemas import (
    LLMConfigCreate,
    LLMConfigListResponse,
    LLMConfigResponse,
    LLMConfigRotateKey,
    LLMConfigSetActive,
    LLMConfigUpdate,
)
from app.llm.service import LLMConfigService, get_llm_service
from app.models.llm import LLMConfig
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()


def _to_response(config: LLMConfig) -> LLMConfigResponse:
    return LLMConfigResponse.model_validate(config)


@router.post("/configs", response_model=LLMConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    body: LLMConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        config = await service.create(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            name=body.name,
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
        )
        await session.commit()
        return _to_response(config)
    except LLMConfigDuplicateNameError as exc:
        logger.warning("LLMConfig name conflict for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Failed to create LLMConfig for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create config"
        ) from exc


@router.get("/configs", response_model=LLMConfigListResponse)
async def list_llm_configs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigListResponse:
    configs = await service.list(session=session, user_id=current_user.id)  # type: ignore[arg-type]
    return LLMConfigListResponse(
        configs=[_to_response(c) for c in configs],
        total=len(configs),
    )


@router.patch("/configs/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: int,
    body: LLMConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    if not body.name and not body.model:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Empty body. Nothing to update.")

    try:
        config = await service.update(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=config_id,
            name=body.name,
            model=body.model,
        )
        await session.commit()
        return _to_response(config)
    except LLMConfigDuplicateNameError as exc:
        logger.warning("LLMConfig name conflict updating config %s for user %s: %s", config_id, current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LLMConfigValidationError as exc:
        logger.warning("Validation error updating LLMConfig %s: %s", config_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for user %s: %s", config_id, current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Failed to update LLMConfig %s: %s", config_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update config"
        ) from exc


@router.put("/configs/{config_id}/key", response_model=LLMConfigResponse)
async def rotate_llm_config_key(
    config_id: int,
    body: LLMConfigRotateKey,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        config = await service.rotate_key(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=config_id,
            api_key=body.api_key,
        )
        await session.commit()
        return _to_response(config)
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for key rotation (user %s): %s", config_id, current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Failed to rotate key for LLMConfig %s: %s", config_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rotate key") from exc


@router.patch("/configs/{config_id}/active", response_model=LLMConfigResponse)
async def set_llm_config_active(
    config_id: int,
    body: LLMConfigSetActive,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> LLMConfigResponse:
    try:
        config = await service.set_active(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=config_id,
            is_active=body.is_active,
        )
        await session.commit()
        return _to_response(config)
    except LLMConfigNotFoundError as exc:
        logger.warning("LLMConfig %s not found for active state update (user %s): %s", config_id, current_user.id, exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.error("Failed to update active state for LLMConfig %s: %s", config_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update config"
        ) from exc


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    service: LLMConfigService = Depends(get_llm_service),
) -> None:
    try:
        deleted = await service.delete(
            session=session,
            user_id=current_user.id,  # type: ignore[arg-type]
            config_id=config_id,
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
        await session.commit()
    except SQLAlchemyError as exc:
        logger.error("Failed to delete LLMConfig %s: %s", config_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete config"
        ) from exc
