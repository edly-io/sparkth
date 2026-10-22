"""Read access to the audit trail: filtered, paginated listing and streamed export.

Reads never touch the append-only guard. Listing is not itself recorded; an
export is, before it streams, so bulk reads of the trail leave a trace (NIST AU-9).
"""

import csv
import io
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from sparkth.lib.audit import record_event_now, scrub_error_detail
from sparkth.lib.audit.context import UserActor
from sparkth.lib.audit.events import AuditChange, AuditExportedAuditEvent, AuditOutcome, AuditTarget
from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.lib.models import AuditEvent
from sparkth.services.audit.constants import EXPORT_BATCH_SIZE, FORMULA_PREFIXES
from sparkth.services.audit.enums import ExportFormat
from sparkth.services.audit.exceptions import AuditEventNotFound
from sparkth.services.audit.schemas import (
    AuditEventExportQuery,
    AuditEventPage,
    AuditEventQuery,
    AuditEventRecord,
    AuditEventSummary,
)

logger = get_logger(__name__)

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


def _render(records: list[AuditEventRecord], export_format: ExportFormat) -> str:
    if export_format is ExportFormat.JSONL:
        return "".join(record.model_dump_json() + "\n" for record in records)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for record in records:
        writer.writerow(_csv_cell(value) for value in record.model_dump(mode="json").values())
    return buffer.getvalue()


async def _read_rows(
    session: AsyncSession, query: AuditEventQuery, *, limit: int, before_id: int | None
) -> tuple[list[AuditEvent], int | None]:
    """Return up to ``limit`` rows older than ``before_id``, newest id first, and the next cursor."""
    statement = _select(query)
    if before_id is not None:
        statement = statement.where(col(AuditEvent.id) < before_id)
    rows = list((await session.exec(statement.order_by(col(AuditEvent.id).desc()).limit(limit + 1))).all())
    page = rows[:limit]
    return page, page[-1].id if len(rows) > limit else None


async def list_events(
    session: AsyncSession, query: AuditEventQuery, *, limit: int, before_id: int | None = None
) -> AuditEventPage:
    """Return up to ``limit`` event summaries matching ``query``, most recently recorded first.

    Orders and pages by row id (keyset) rather than offset, so a page stays stable while
    new events are appended. ``next_before_id`` is ``None`` on the last page. Read one
    event in full with :func:`get_event`.
    """
    rows, next_before_id = await _read_rows(session, query, limit=limit, before_id=before_id)
    return AuditEventPage(items=[AuditEventSummary.model_validate(row) for row in rows], next_before_id=next_before_id)


async def get_event(session: AsyncSession, event_id: int) -> AuditEventRecord:
    """Return the event with ``event_id`` in full; raise ``AuditEventNotFound`` if there is none."""
    row = await session.get(AuditEvent, event_id)
    if row is None:
        raise AuditEventNotFound(f"Audit event {event_id} not found")
    return AuditEventRecord.model_validate(row)


def list_categories() -> list[str]:
    """Return the categories of every registered audit event type, sorted.

    Read from the ``AUDIT_EVENTS`` registry, so a category a plugin registers is
    offered as soon as its event types are.
    """
    return sorted({event_type.partition(".")[0] for event_type in AUDIT_EVENTS.iter_keys()})


def _export_event(
    actor: UserActor, query: AuditEventExportQuery, outcome: AuditOutcome, error_detail: str | None = None
) -> AuditExportedAuditEvent:
    return AuditExportedAuditEvent(
        outcome=outcome,
        actor=actor,
        target=AuditTarget(type="audit_events"),
        change=AuditChange(new=_create_audit_snapshot(query)),
        error_detail=error_detail,
    )


async def record_export(actor: UserActor, query: AuditEventExportQuery) -> None:
    """Commit ``audit.exported`` for ``actor`` before any row leaves the system.

    Fail-closed: if the record cannot be written the error propagates and the
    export never starts.
    """
    await record_event_now(_export_event(actor, query, AuditOutcome.SUCCESS))


async def export_lines(actor: UserActor, query: AuditEventExportQuery) -> AsyncIterator[str]:
    """Stream every event matching ``query``, most recently recorded first, as CSV or JSON Lines.

    Fetches ``EXPORT_BATCH_SIZE`` rows at a time, each batch in a session of its
    own that closes before the batch is sent, so a slow client never holds a pool
    connection. The keyset cursor carries the position from one batch to the next.
    A batch that cannot be read cuts the file short, so it is recorded as a failed
    ``audit.exported`` for ``actor`` before the error propagates.
    """
    if query.export_format is ExportFormat.CSV:
        yield ",".join(CSV_COLUMNS) + "\r\n"
    before_id: int | None = None
    while True:
        try:
            async with session_scope() as session:
                rows, next_before_id = await _read_rows(session, query, limit=EXPORT_BATCH_SIZE, before_id=before_id)
                records = [AuditEventRecord.model_validate(row) for row in rows]
        except SQLAlchemyError as exc:
            logger.exception("Audit export by user %s failed before id %s", actor.id, before_id)
            await record_event_now(_export_event(actor, query, AuditOutcome.FAILURE, scrub_error_detail(exc)))
            raise
        yield _render(records, query.export_format)
        if next_before_id is None:
            return
        before_id = next_before_id
