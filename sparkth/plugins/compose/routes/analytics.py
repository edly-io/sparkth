"""Compose authoring analytics read, gated by ``analytics.read`` at the Compose plugin scope."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import RangeQuery
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ
from sparkth.lib.permissions.scopes import PLUGIN
from sparkth.lib.routes import platform_wide
from sparkth.plugins.compose.analytics.reads import ComposeActivityPoint, get_compose_activity
from sparkth.plugins.compose.constants import COMPOSE_PLUGIN_NAME

router = APIRouter()


@router.get(
    "/analytics/activity",
    response_model=list[ComposeActivityPoint],
    dependencies=[Depends(ANALYTICS_READ.require_for_object(PLUGIN, COMPOSE_PLUGIN_NAME))],
)
@platform_wide
async def compose_activity(
    query: Annotated[RangeQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[ComposeActivityPoint]:
    """Return compose authoring event counts per bucket, event type, dimension and outcome.

    Sparse: combinations with no events are omitted; consumers zero-fill. Counts are lower
    bounds: events queued on background tasks are lost when a route raises. Answers whatever
    the plugin switches say.
    """
    return await get_compose_activity(session, query.from_, query.to, query.bucket)
