"""Run one learner action and publish its events, recording a failure in the author's own preview.

The socket and the action POST route both run actions through ``perform_action``. A failure is
recorded only for a preview launch, never for a learner in a course, and only so the author's
agent can read it. Recording is best-effort: a failed write is logged and the action's own error
still reaches the caller.
"""

import asyncio
import json
from uuid import UUID

from pxc.lib.fields import FieldType
from pxc.lib.runtime import ActivityRuntime
from sqlalchemy.exc import SQLAlchemyError

from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_PREVIEW_COURSE_ID, PXC_TRUNCATED_MARKER
from sparkth.plugins.pxc.enums import PreviewPermission, PxcFailureKind
from sparkth.plugins.pxc.event_bus import publish_events
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.models import PxcActionFailure
from sparkth.plugins.pxc.runtime import run_action
from sparkth.plugins.pxc.store import insert_action_failure
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)


async def perform_action(
    runtime: ActivityRuntime, claims: LaunchClaims, action_name: str, action_value: FieldType
) -> None:
    """Run ``action_name`` on ``runtime`` in a worker thread and publish its events.

    Raises:
        PxcActionRejected: if the manifest does not accept this action or value.
        PxcSandboxFailure: if the sandbox failed.
    """
    try:
        events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    except PxcActionRejected as err:
        await _record_preview_failure(claims, PxcFailureKind.REJECTED, action_name, action_value, str(err))
        raise
    except PxcSandboxFailure as err:
        await _record_preview_failure(claims, PxcFailureKind.FAILED, action_name, action_value, err.error_text)
        raise
    await publish_events(claims.activity, claims.activity_instance, events)


async def _record_preview_failure(
    claims: LaunchClaims, kind: PxcFailureKind, action_name: str, action_value: FieldType, error: str
) -> None:
    """Record a failed action of an author's preview; any other launch's failure is not stored."""
    if claims.course_id != PXC_PREVIEW_COURSE_ID:
        return
    settings = get_pxc_settings()
    failure = PxcActionFailure(
        activity_id=UUID(claims.activity),
        revision=claims.revision,
        kind=kind,
        action=action_name,
        # A preview launches only as play or edit, so its permission is always a PreviewPermission.
        permission=PreviewPermission(claims.permission.value),
        value=_cut(json.dumps(action_value), settings.error_limit),
        error=_cut(error, settings.error_limit),
    )
    try:
        async with session_scope() as session:
            await insert_action_failure(session, failure, settings.action_failure_limit)
    except SQLAlchemyError as err:
        logger.warning(
            "Could not record failed preview action %s of PXC activity %s: %s", action_name, claims.activity, err
        )


def _cut(text: str, limit: int) -> str:
    """``text``, or its first ``limit`` characters ended with ``PXC_TRUNCATED_MARKER`` when it is longer."""
    return text if len(text) <= limit else text[:limit] + PXC_TRUNCATED_MARKER
