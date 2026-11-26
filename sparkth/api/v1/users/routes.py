"""Users API routes: list and look up users, gated by ``user.read`` at the ``global`` scope."""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.users.schemas import UserSummary
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import USER_READ
from sparkth.services.users.service import get_user, list_users

router = APIRouter()


@router.get(
    "",
    response_model=list[UserSummary],
    dependencies=[Depends(USER_READ.require_in_global_scope())],
)
async def list_user_summaries(
    search: str | None = Query(None, min_length=1, max_length=50),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> list[UserSummary]:
    """List active users by username, keeping those whose name, username or email contains ``search``."""
    users = await list_users(search, limit, offset, session)
    return [UserSummary.model_validate(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserSummary,
    dependencies=[Depends(USER_READ.require_in_global_scope())],
)
async def get_user_summary(user_id: int, session: AsyncSession = Depends(get_async_session)) -> UserSummary:
    """Return one active user, or 404 when there is none."""
    return UserSummary.model_validate(await get_user(user_id, session))
