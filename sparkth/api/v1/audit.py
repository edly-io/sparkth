"""Audit trail read API: administrators query recorded audit events.

Every endpoint is gated by the ``audit.read`` permission in the global scope. The
listing is keyset-paginated, newest first.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import AUDIT_READ
from sparkth.services.audit_log import AuditEventPage, AuditEventPageQuery, AuditLogService

router = APIRouter(dependencies=[Depends(AUDIT_READ.require_in_global_scope())])


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
