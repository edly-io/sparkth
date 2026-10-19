"""Read-side query over Drive document processing.

Reads the ``googledrive_documents_daily`` continuous aggregate through ``read_rollup``; its
``dims`` and ``sums`` must match the aggregate's ``outcome`` / ``seconds_total`` definition.
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sparkth.lib.analytics import Bucket, read_rollup
from sparkth.plugins.googledrive.analytics.events import READY_OUTCOMES, GoogleDriveDocumentProcessed


class DriveDocumentsPoint(BaseModel):
    """Documents that reached ``outcome`` in one bucket. ``bucket`` is the UTC start, ``YYYY-MM-DD``."""

    bucket: str
    outcome: str | None = None
    ready: bool
    """Whether ``outcome`` leaves the document usable in chat."""
    document_count: int
    seconds_total: int
    """Sum of ``seconds_to_final``."""


async def get_drive_documents(
    session: AsyncSession, from_: date, to: date, bucket: Bucket
) -> list[DriveDocumentsPoint]:
    """Return processed-document counts and summed seconds per ``bucket`` and outcome. Sparse."""
    rows = await read_rollup(
        session,
        aggregate="googledrive_documents_daily",
        event_types=(GoogleDriveDocumentProcessed.event_type,),
        dims={"outcome": "outcome"},
        count_column="document_count",
        sums={"seconds_total": "seconds_to_final"},
        from_=from_,
        to=to,
        bucket=bucket,
    )
    return [DriveDocumentsPoint.model_validate({**r, "ready": r["outcome"] in READY_OUTCOMES}) for r in rows]
