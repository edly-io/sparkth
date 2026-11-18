"""Drive document analytics read, gated by ``analytics.read`` at the Google Drive plugin scope."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import RangeQuery
from sparkth.lib.db import get_analytics_session
from sparkth.lib.permissions import ANALYTICS_READ
from sparkth.lib.permissions.scopes import PLUGIN
from sparkth.lib.routes import platform_wide
from sparkth.plugins.googledrive.analytics.reads import DriveDocumentsPoint, get_drive_documents
from sparkth.plugins.googledrive.constants import GOOGLE_DRIVE_PLUGIN_NAME

router = APIRouter()


@router.get(
    "/analytics/documents",
    response_model=list[DriveDocumentsPoint],
    dependencies=[Depends(ANALYTICS_READ.require_for_object(PLUGIN, GOOGLE_DRIVE_PLUGIN_NAME))],
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
