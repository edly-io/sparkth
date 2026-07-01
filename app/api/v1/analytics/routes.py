"""Analytics emission gateway endpoint — the single validating write path for client producers.

Server-side code calls `ingest_event` directly.
This endpoint is for client-emittable event types only; server-only types are
rejected with ``403``.

``occurred_at`` is always server-stamped here — clients cannot back/forward-date
events via the HTTP path. Trusted server-side callers that need to control
``occurred_at`` call ``ingest_event()`` directly.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.analytics.schemas import EmitEventRequest, EmitEventResponse
from app.core.analytics.registry import EventRegistry
from app.lib.analytics import UnknownEventTypeError, ingest_event
from app.lib.auth import get_current_user
from app.lib.db import get_analytics_session
from app.lib.log import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", response_model=EmitEventResponse, status_code=status.HTTP_202_ACCEPTED)
async def emit_event(
    event: EmitEventRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_analytics_session),
) -> EmitEventResponse:
    """Validate an analytics event against its versioned schema and land it.

    Only client-emittable event types are accepted here. Server-only types (e.g.
    ``assessment.submitted``) must be emitted by server-side callers via
    `ingest_event` directly.

    ``occurred_at`` is always set to the server's current time; the client cannot
    supply it. Unknown event types and invalid payloads are rejected with ``422``.
    """
    try:
        if EventRegistry().is_server_only(event.event_type, event.version):
            logger.warning(
                "Rejected client attempt to emit server-only event %s v%s",
                event.event_type,
                event.version,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Event type is not client-emittable",
            )
    except UnknownEventTypeError as exc:
        logger.warning("Rejected unknown analytics event %s v%s", event.event_type, event.version)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        await ingest_event(
            session,
            event.event_type,
            event.version,
            event.payload,
            str(current_user.id) if current_user.id is not None else None,
            occurred_at=None,  # always server-stamped on the HTTP path
        )
    except UnknownEventTypeError as exc:
        logger.warning("Rejected unknown analytics event %s v%s", event.event_type, event.version)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ValidationError as exc:
        logger.warning("Rejected invalid payload for %s v%s", event.event_type, event.version)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event payload failed schema validation",
        ) from exc

    return EmitEventResponse(accepted=True)
