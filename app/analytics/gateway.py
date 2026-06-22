"""The analytics emission gateway — validate an event, then land it in raw_events.

The single write path for analytics events: resolve the versioned schema, validate
the payload against it, and insert one immutable row into ``raw_events``. Callers
provide the analytics session — the API injects ``get_analytics_session``; future
background callers wrap ``analytics_session_scope()``.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

import app.analytics.schemas  # noqa: F401 -- populates event_registry on import
from app.analytics.models import raw_events
from app.analytics.registry import event_registry
from app.lib.log import get_logger

logger = get_logger(__name__)


async def ingest_event(
    session: AsyncSession,
    event_type: str,
    version: int,
    payload: dict[str, Any],
    actor_id: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    """Validate ``payload`` against the registered schema and land it in ``raw_events``.

    Args:
        session: An async session bound to the analytics database.
        event_type: The base event name, e.g. ``"assessment.submitted"``.
        version: The schema version, e.g. ``1``.
        payload: The raw event body to validate.
        actor_id: The authenticated user id, stored for provenance.
        occurred_at: When the event happened; defaults to ``now(UTC)``.

    Raises:
        UnknownEventTypeError: No schema is registered for ``(event_type, version)``.
        pydantic.ValidationError: The payload does not satisfy the schema.
        sqlalchemy.exc.SQLAlchemyError: The insert failed.
    """
    schema = event_registry.resolve(event_type, version)
    validated = schema.model_validate(payload)

    try:
        await session.exec(
            raw_events.insert().values(
                occurred_at=occurred_at or datetime.now(timezone.utc),
                event_type=event_type,
                event_version=version,
                actor_id=actor_id,
                payload=validated.model_dump(mode="json"),
            )
        )
        await session.commit()
    except SQLAlchemyError:
        logger.exception("Failed to land analytics event %s v%s", event_type, version)
        await session.rollback()
        raise
