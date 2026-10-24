"""Saved Explore views: each user's own, gated by ``analytics.read``. Another user's view is a 404."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, StringConstraints
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.analytics_view import AnalyticsView
from sparkth.core.models.user import User
from sparkth.lib.db import get_async_session
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.permissions import ANALYTICS_READ
from sparkth.services.analytics_views import (
    AnalyticsViewAlreadyExists,
    AnalyticsViewNotFound,
    create_view,
    delete_view,
    get_view,
    list_views,
    update_view,
)

register_exception_handler(AnalyticsViewNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(AnalyticsViewAlreadyExists, status.HTTP_409_CONFLICT)

ViewName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Reader = Annotated[User, Depends(ANALYTICS_READ.require_in_global_scope())]
Session = Annotated[AsyncSession, Depends(get_async_session)]

router = APIRouter()


class AnalyticsViewIn(BaseModel):
    """A view to save."""

    name: ViewName
    config: dict[str, Any]


class AnalyticsViewPatch(BaseModel):
    """Parts of a view to change."""

    name: ViewName | None = None
    config: dict[str, Any] | None = None


class AnalyticsViewOut(BaseModel):
    """A saved view."""

    id: uuid.UUID
    name: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


def _out(view: AnalyticsView) -> AnalyticsViewOut:
    return AnalyticsViewOut.model_validate(view, from_attributes=True)


@router.get("", response_model=list[AnalyticsViewOut])
async def list_analytics_views(user: Reader, session: Session) -> list[AnalyticsViewOut]:
    """Return the caller's saved views, by name."""
    return [_out(v) for v in await list_views(session, user.id)]  # type: ignore[arg-type]


@router.post("", response_model=AnalyticsViewOut, status_code=status.HTTP_201_CREATED)
async def create_analytics_view(body: AnalyticsViewIn, user: Reader, session: Session) -> AnalyticsViewOut:
    """Save an Explore config as a new view."""
    return _out(await create_view(session, user.id, body.name, body.config))  # type: ignore[arg-type]


@router.get("/{view_id}", response_model=AnalyticsViewOut)
async def get_analytics_view(view_id: uuid.UUID, user: Reader, session: Session) -> AnalyticsViewOut:
    """Return one of the caller's views."""
    return _out(await get_view(session, user.id, view_id))  # type: ignore[arg-type]


@router.patch("/{view_id}", response_model=AnalyticsViewOut)
async def update_analytics_view(
    view_id: uuid.UUID, body: AnalyticsViewPatch, user: Reader, session: Session
) -> AnalyticsViewOut:
    """Rename a view and/or replace its config."""
    return _out(await update_view(session, user.id, view_id, body.name, body.config))  # type: ignore[arg-type]


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analytics_view(view_id: uuid.UUID, user: Reader, session: Session) -> None:
    """Delete one of the caller's views."""
    await delete_view(session, user.id, view_id)  # type: ignore[arg-type]
