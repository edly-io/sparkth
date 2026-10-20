"""Read access to the audit trail: filtered, paginated listing.

Reads never touch the append-only guard, and listing is not itself recorded.
"""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from sparkth.core.audit.models import AuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.services.audit_log.types import AuditEventPage, AuditEventQuery, AuditEventRecord

# Filters that match a column of the same name exactly; the time range is the only other kind.
_EXACT_FILTERS = AuditEventQuery.model_fields.keys() - {"from_", "to"}


def _select(query: AuditEventQuery) -> SelectOfScalar[AuditEvent]:
    statement = select(AuditEvent).filter_by(**query.model_dump(include=_EXACT_FILTERS, exclude_none=True))
    if query.from_ is not None:
        statement = statement.where(col(AuditEvent.occurred_at) >= query.from_)
    if query.to is not None:
        statement = statement.where(col(AuditEvent.occurred_at) <= query.to)
    return statement


class AuditLogService:
    @staticmethod
    async def list_events(
        session: AsyncSession, query: AuditEventQuery, *, limit: int, before_id: int | None = None
    ) -> AuditEventPage:
        """Return up to ``limit`` events matching ``query``, newest first.

        Pages by row id (keyset) rather than offset, so a page stays stable while new
        events are appended. ``next_before_id`` is ``None`` on the last page.
        """
        statement = _select(query)
        if before_id is not None:
            statement = statement.where(col(AuditEvent.id) < before_id)
        rows = (await session.exec(statement.order_by(col(AuditEvent.id).desc()).limit(limit + 1))).all()
        items = [AuditEventRecord.model_validate(row) for row in rows[:limit]]
        return AuditEventPage(items=items, next_before_id=items[-1].id if len(rows) > limit else None)

    @staticmethod
    def categories() -> list[str]:
        """Return the categories of every registered audit event type, sorted.

        Read from the ``AUDIT_EVENTS`` registry, so a category a plugin registers is
        offered as soon as its event types are.
        """
        return sorted({event_type.partition(".")[0] for event_type in AUDIT_EVENTS.iter_keys()})
