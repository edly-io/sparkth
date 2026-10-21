"""Audit trail read API: administrators query and export recorded audit events.

Every endpoint is gated by the ``audit.read`` permission in the global scope. The
listing is keyset-paginated, most recently recorded first; the export streams every
matching event as CSV or JSON Lines and records ``audit.exported`` before the first
row leaves.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit.context import UserActor
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User, utc_now
from sparkth.lib.permissions import AUDIT_READ
from sparkth.services import audit as audit_service
from sparkth.services.audit import AuditEventExportQuery, AuditEventPage, AuditEventPageQuery, ExportFormat

router = APIRouter(dependencies=[Depends(AUDIT_READ.require_in_global_scope())])

_MEDIA_TYPES = {ExportFormat.CSV: "text/csv", ExportFormat.JSONL: "application/x-ndjson"}


@router.get("/events", response_model=AuditEventPage)
async def list_events(
    query: Annotated[AuditEventPageQuery, Query()],
    session: AsyncSession = Depends(get_async_session),
) -> AuditEventPage:
    """Return audit events matching every given filter, most recently recorded first.

    Pass the response's `next_before_id` as `before_id` to fetch the next page; it is
    null on the last page.
    """
    return await audit_service.list_events(session, query, limit=query.limit, before_id=query.before_id)


@router.get("/categories", response_model=list[str])
async def list_categories() -> list[str]:
    """Return every category an audit event can carry, sorted, to filter the listing by."""
    return audit_service.list_categories()


@router.get("/events/export", response_class=StreamingResponse)
async def export_events(
    query: Annotated[AuditEventExportQuery, Query()],
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Download every audit event matching the filters as CSV or JSON Lines, most recently recorded first.

    The export itself is recorded as an `audit.exported` event naming the filters, and
    again as a failure if the stream is cut short.
    """
    actor = UserActor(id=str(current_user.id), label=current_user.username)
    await audit_service.record_export(actor, query)
    filename = f"audit-events-{utc_now():%Y%m%dT%H%M%SZ}.{query.export_format.value}"
    return StreamingResponse(
        audit_service.export_lines(actor, query),
        media_type=_MEDIA_TYPES[query.export_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
