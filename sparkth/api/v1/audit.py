"""Audit trail read API: administrators query and export recorded audit events.

Every endpoint is gated by the ``audit.read`` permission in the global scope. The
listing is keyset-paginated, newest first; the export streams every matching event
as CSV or JSON Lines and records ``audit.exported`` before the first row leaves.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.base import utc_now
from sparkth.core.models.user import User
from sparkth.lib.audit.context import UserActor
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import AUDIT_READ
from sparkth.services.audit_log import (
    AuditEventExportQuery,
    AuditEventPage,
    AuditEventPageQuery,
    AuditLogService,
    ExportFormat,
)

router = APIRouter(dependencies=[Depends(AUDIT_READ.require_in_global_scope())])

_MEDIA_TYPES = {ExportFormat.CSV: "text/csv", ExportFormat.JSONL: "application/x-ndjson"}


@router.get("/events", response_model=AuditEventPage)
async def list_events(
    query: Annotated[AuditEventPageQuery, Query()],
    session: AsyncSession = Depends(get_async_session),
) -> AuditEventPage:
    """Return audit events matching every given filter, newest first.

    Pass the response's `next_before_id` as `before_id` to fetch the next page; it is
    null on the last page.
    """
    return await AuditLogService.list_events(session, query, limit=query.limit, before_id=query.before_id)


@router.get("/categories", response_model=list[str])
async def list_categories() -> list[str]:
    """Return every category an audit event can carry, sorted, to filter the listing by."""
    return AuditLogService.categories()


@router.get("/events/export", response_class=StreamingResponse)
async def export_events(
    query: Annotated[AuditEventExportQuery, Query()],
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download every audit event matching the filters as CSV or JSON Lines, newest first.

    The export itself is recorded as an `audit.exported` event naming the filters.
    """
    await AuditLogService.record_export(UserActor(id=str(current_user.id), label=current_user.username), query)
    filename = f"audit-events-{utc_now():%Y%m%dT%H%M%SZ}.{query.export_format.value}"
    return StreamingResponse(
        AuditLogService.export_lines(query),
        media_type=_MEDIA_TYPES[query.export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
