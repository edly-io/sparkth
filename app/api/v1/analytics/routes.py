"""Analytics emission gateway endpoint — the single validating write path."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.analytics.schemas import EmitEventRequest, EmitEventResponse
from app.api.v1.auth import get_current_user
from app.lib.analytics import UnknownEventTypeError, ingest_event
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

    Fire-and-forget for the producer: does the minimum (validate + insert) and
    returns ``202``. Unknown event types and invalid payloads are rejected with
    ``422``.
    """
    try:
        await ingest_event(
            session,
            event.event_type,
            event.version,
            event.payload,
            str(current_user.id) if current_user.id is not None else None,
            event.occurred_at,
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
