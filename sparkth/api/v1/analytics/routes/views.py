"""Saved Explore views sub-router (mounted at ``/views``): each user's own, gated by
``analytics.read`` and, like Explore itself, ``user.read``. Another user's view is a 404."""

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.analytics.schemas import AnalyticsViewIn, AnalyticsViewOut, AnalyticsViewPatch
from sparkth.lib.analytics import create_view, delete_view, get_view, list_views, update_view
from sparkth.lib.db import get_async_session
from sparkth.lib.models import AnalyticsView, User
from sparkth.lib.permissions import ANALYTICS_READ, USER_READ

Session = Annotated[AsyncSession, Depends(get_async_session)]
Reader = Annotated[User, Depends(ANALYTICS_READ.require_in_global_scope())]

router = APIRouter(dependencies=[Depends(USER_READ.require_in_global_scope())])


def _view_response(view: AnalyticsView) -> AnalyticsViewOut:
    return AnalyticsViewOut.model_validate(view, from_attributes=True)


@router.get("", response_model=list[AnalyticsViewOut])
async def list_analytics_views(user: Reader, session: Session) -> list[AnalyticsViewOut]:
    """Return the caller's saved views, by name."""
    return [_view_response(view) for view in await list_views(session, cast(int, user.id))]


@router.post("", response_model=AnalyticsViewOut, status_code=status.HTTP_201_CREATED)
async def create_analytics_view(body: AnalyticsViewIn, user: Reader, session: Session) -> AnalyticsViewOut:
    """Save an Explore config as a new view."""
    return _view_response(await create_view(session, cast(int, user.id), body.name, body.config))


@router.get("/{view_id}", response_model=AnalyticsViewOut)
async def get_analytics_view(view_id: uuid.UUID, user: Reader, session: Session) -> AnalyticsViewOut:
    """Return one of the caller's views."""
    return _view_response(await get_view(session, cast(int, user.id), view_id))


@router.patch("/{view_id}", response_model=AnalyticsViewOut)
async def update_analytics_view(
    view_id: uuid.UUID, body: AnalyticsViewPatch, user: Reader, session: Session
) -> AnalyticsViewOut:
    """Rename a view and/or replace its config."""
    return _view_response(await update_view(session, cast(int, user.id), view_id, body.name, body.config))


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analytics_view(view_id: uuid.UUID, user: Reader, session: Session) -> None:
    """Delete one of the caller's views."""
    await delete_view(session, cast(int, user.id), view_id)
