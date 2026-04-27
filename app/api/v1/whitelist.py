from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import require_superuser
from app.core.db import get_async_session
from app.models.user import User
from app.schemas import WhitelistedEmailCreate, WhitelistedEmailResponse
from app.services.whitelist import WhitelistService

router = APIRouter()


@router.get("/", response_model=list[WhitelistedEmailResponse])
async def list_whitelist(
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> list[WhitelistedEmailResponse]:
    entries = await WhitelistService.list_entries(session)
    return [WhitelistedEmailResponse.model_validate(e) for e in entries]


@router.post("/", response_model=WhitelistedEmailResponse, status_code=status.HTTP_201_CREATED)
async def add_whitelist_entry(
    payload: WhitelistedEmailCreate,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> WhitelistedEmailResponse:
    try:
        entry = await WhitelistService.add_entry(
            session,
            value=payload.value,
            added_by_id=current_user.id,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)
    return WhitelistedEmailResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_whitelist_entry(
    entry_id: int,
    current_user: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    try:
        await WhitelistService.remove_entry(session, entry_id=entry_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whitelist entry not found",
        ) from None
