"""Chat authoring analytics read, gated by ``analytics.read``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import RangeQuery
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ
from sparkth.plugins.chat.analytics.reads import ChatActivityPoint, get_chat_activity

router = APIRouter()


@router.get(
    "/analytics/activity",
    response_model=list[ChatActivityPoint],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
async def chat_activity(
    query: Annotated[RangeQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[ChatActivityPoint]:
    """Return chat authoring event counts per bucket, event type, dimension and outcome.

    Sparse: combinations with no events are omitted; consumers zero-fill. Counts are lower
    bounds: events queued on background tasks are lost when a route raises. Like every chat
    route, answers 403 when the caller has the chat plugin disabled.
    """
    return await get_chat_activity(session, query.from_, query.to, query.bucket)
