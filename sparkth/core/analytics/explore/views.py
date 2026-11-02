"""Saved Explore views. Every query filters by owner, so another user's view reads as missing."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.exceptions import AnalyticsViewAlreadyExists, AnalyticsViewNotFound
from sparkth.core.analytics.explore.models import AnalyticsView
from sparkth.core.analytics.explore.schemas import ViewConfig
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


async def list_views(session: AsyncSession, owner_id: int) -> list[AnalyticsView]:
    """The owner's views, by name."""
    result = await session.exec(
        select(AnalyticsView).where(AnalyticsView.owner_id == owner_id).order_by(col(AnalyticsView.name))
    )
    return list(result.all())


async def get_view(session: AsyncSession, owner_id: int, view_id: uuid.UUID) -> AnalyticsView:
    """The owner's view with this id.

    Raises:
        AnalyticsViewNotFound: No such view for this owner.
    """
    view = (
        await session.exec(select(AnalyticsView).where(AnalyticsView.id == view_id, AnalyticsView.owner_id == owner_id))
    ).first()
    if view is None:
        raise AnalyticsViewNotFound(f"Analytics view {view_id} not found")
    return view


def _stored(config: ViewConfig) -> dict[str, object]:
    return config.model_dump(mode="json", by_alias=True)


async def _save(session: AsyncSession, view: AnalyticsView) -> AnalyticsView:
    name, owner_id = view.name, view.owner_id  # a rollback expires the instance
    session.add(view)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning("Analytics view name %r taken for owner %s: %s", name, owner_id, exc)
        raise AnalyticsViewAlreadyExists(f"A view named {name!r} already exists") from exc
    await session.refresh(view)
    return view


async def create_view(session: AsyncSession, owner_id: int, name: str, config: ViewConfig) -> AnalyticsView:
    """Save a new view.

    Raises:
        AnalyticsViewAlreadyExists: The owner already has a view with this name.
    """
    return await _save(session, AnalyticsView(owner_id=owner_id, name=name, config=_stored(config)))


async def update_view(
    session: AsyncSession,
    owner_id: int,
    view_id: uuid.UUID,
    name: str | None,
    config: ViewConfig | None,
) -> AnalyticsView:
    """Rename a view and/or replace its config; ``None`` leaves that part as is.

    Raises:
        AnalyticsViewNotFound: No such view for this owner.
        AnalyticsViewAlreadyExists: The new name is taken by another of the owner's views.
    """
    view = await get_view(session, owner_id, view_id)
    if name is not None:
        view.name = name
    if config is not None:
        view.config = _stored(config)
    view.update_timestamp()
    return await _save(session, view)


async def delete_view(session: AsyncSession, owner_id: int, view_id: uuid.UUID) -> None:
    """Delete a view.

    Raises:
        AnalyticsViewNotFound: No such view for this owner.
    """
    await session.delete(await get_view(session, owner_id, view_id))
    await session.commit()
