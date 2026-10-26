"""Drive document analytics read, gated by ``analytics.read``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import RangeQuery
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ
from sparkth.lib.routes import platform_wide
from sparkth.plugins.googledrive.analytics.reads import DriveDocumentsPoint, get_drive_documents

router = APIRouter()


@router.get(
    "/analytics/documents",
    response_model=list[DriveDocumentsPoint],
    dependencies=[Depends(ANALYTICS_READ.require_in_global_scope())],
)
@platform_wide
async def drive_documents(
    query: Annotated[RangeQuery, Query()],
    session: AsyncSession = Depends(get_analytics_session),
) -> list[DriveDocumentsPoint]:
    """Return processed Drive documents per bucket and outcome, with summed seconds to final.

    Sparse: consumers zero-fill. Answers whatever the plugin switches say.
    """
    return await get_drive_documents(session, query.from_, query.to, query.bucket)
