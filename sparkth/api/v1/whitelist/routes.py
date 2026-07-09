from typing import cast

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import (
    EMAIL_WHITELIST_CREATE,
    EMAIL_WHITELIST_DELETE,
    EMAIL_WHITELIST_READ,
)
from sparkth.lib.permissions.scopes import WHITELIST
from sparkth.schemas import WhitelistedEmailCreate, WhitelistedEmailResponse
from sparkth.services.whitelist import WhitelistService

router = APIRouter()


@router.get(
    "/",
    response_model=list[WhitelistedEmailResponse],
    dependencies=[Depends(EMAIL_WHITELIST_READ.require(WHITELIST))],
)
async def list_whitelist(
    session: AsyncSession = Depends(get_async_session),
) -> list[WhitelistedEmailResponse]:
    entries = await WhitelistService.list_entries(session)
    return [WhitelistedEmailResponse.model_validate(e) for e in entries]


@router.post("/", response_model=WhitelistedEmailResponse, status_code=status.HTTP_201_CREATED)
async def add_whitelist_entry(
    payload: WhitelistedEmailCreate,
    current_user: User = Depends(EMAIL_WHITELIST_CREATE.require(WHITELIST)),
    session: AsyncSession = Depends(get_async_session),
) -> WhitelistedEmailResponse:
    entry = await WhitelistService.add_entry(
        session,
        value=payload.value,
        added_by_id=cast(int, current_user.id),
    )
    return WhitelistedEmailResponse.model_validate(entry)


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(EMAIL_WHITELIST_DELETE.require(WHITELIST))],
)
async def remove_whitelist_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    await WhitelistService.remove_entry(session, entry_id=entry_id)
