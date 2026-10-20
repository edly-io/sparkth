"""Read access to the audit trail: filtered, paginated listing and streamed export.

Reads never touch the append-only guard. Listing is not itself recorded; an
export is, before it streams, so bulk reads of the trail leave a trace (NIST AU-9).
"""

import csv
import io
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from sparkth.lib.audit import record_event_now
from sparkth.lib.audit.context import UserActor
from sparkth.lib.audit.events import AuditChange, AuditExportedAuditEvent, AuditOutcome, AuditTarget
from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.db import session_scope
from sparkth.lib.models import AuditEvent
from sparkth.services.audit.constants import EXPORT_BATCH_SIZE, FORMULA_PREFIXES
from sparkth.services.audit.enums import ExportFormat
from sparkth.services.audit.schemas import AuditEventExportQuery, AuditEventPage, AuditEventQuery, AuditEventRecord

CSV_COLUMNS = list(AuditEventRecord.model_fields)

# Filters that match a column of the same name exactly; the time range is the only other kind.
_EXACT_FILTERS = AuditEventQuery.model_fields.keys() - {"from_", "to"}


def _select(query: AuditEventQuery) -> SelectOfScalar[AuditEvent]:
    statement = select(AuditEvent).filter_by(**query.model_dump(include=_EXACT_FILTERS, exclude_none=True))
    if query.from_ is not None:
        statement = statement.where(col(AuditEvent.occurred_at) >= query.from_)
    if query.to is not None:
        statement = statement.where(col(AuditEvent.occurred_at) <= query.to)
    return statement


def _create_audit_snapshot(query: AuditEventExportQuery) -> dict[str, Any]:
    return {
        "format": query.export_format.value,
        "filters": query.model_dump(mode="json", by_alias=True, exclude_none=True, exclude={"export_format"}),
    }


def _csv_cell(value: Any) -> Any:
    """Render one CSV cell, quoting a string a spreadsheet would run as a formula (CWE-1236)."""
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _render(page: AuditEventPage, export_format: ExportFormat) -> str:
    if export_format is ExportFormat.JSONL:
        return "".join(record.model_dump_json() + "\n" for record in page.items)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for record in page.items:
        writer.writerow(_csv_cell(value) for value in record.model_dump(mode="json").values())
    return buffer.getvalue()


async def list_events(
    session: AsyncSession, query: AuditEventQuery, *, limit: int, before_id: int | None = None
) -> AuditEventPage:
    """Return up to ``limit`` events matching ``query``, most recently recorded first.

    Orders and pages by row id (keyset) rather than offset, so a page stays stable while
    new events are appended. ``next_before_id`` is ``None`` on the last page.
    """
    statement = _select(query)
    if before_id is not None:
        statement = statement.where(col(AuditEvent.id) < before_id)
    rows = (await session.exec(statement.order_by(col(AuditEvent.id).desc()).limit(limit + 1))).all()
    items = [AuditEventRecord.model_validate(row) for row in rows[:limit]]
    return AuditEventPage(items=items, next_before_id=items[-1].id if len(rows) > limit else None)


def list_categories() -> list[str]:
    """Return the categories of every registered audit event type, sorted.

    Read from the ``AUDIT_EVENTS`` registry, so a category a plugin registers is
    offered as soon as its event types are.
    """
    return sorted({event_type.partition(".")[0] for event_type in AUDIT_EVENTS.iter_keys()})


async def record_export(actor: UserActor, query: AuditEventExportQuery) -> None:
    """Commit ``audit.exported`` for ``actor`` before any row leaves the system.

    Fail-closed: if the record cannot be written the error propagates and the
    export never starts.
    """
    await record_event_now(
        AuditExportedAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            actor=actor,
            target=AuditTarget(type="audit_events"),
            change=AuditChange(new=_create_audit_snapshot(query)),
        )
    )


async def export_lines(query: AuditEventExportQuery) -> AsyncIterator[str]:
    """Stream every event matching ``query``, most recently recorded first, as CSV or JSON Lines.

    Fetches ``EXPORT_BATCH_SIZE`` rows at a time, each batch in a session of its
    own that closes before the batch is sent, so a slow client never holds a pool
    connection. The keyset cursor carries the position from one batch to the next.
    """
    if query.export_format is ExportFormat.CSV:
        yield ",".join(CSV_COLUMNS) + "\r\n"
    before_id: int | None = None
    while True:
        async with session_scope() as session:
            page = await list_events(session, query, limit=EXPORT_BATCH_SIZE, before_id=before_id)
        yield _render(page, query.export_format)
        if page.next_before_id is None:
            return
        before_id = page.next_before_id
