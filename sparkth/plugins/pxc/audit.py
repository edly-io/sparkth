"""Audit event types owned by the PXC plugin.

An author permanently deleting one of their generated activities. Snapshots carry the activity's
title and whether it was placed, never its content.
"""

from dataclasses import dataclass
from typing import ClassVar

from sparkth.lib.audit.events import MutationAuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS

PXC_ACTIVITY_TARGET = "pxc_activity"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class PxcActivityDeletedAuditEvent(MutationAuditEvent):
    """An author deleted an activity and its row was removed.

    ``change.old`` carries the activity's ``title`` and whether it was ``placed``.
    """

    event_type: ClassVar[str] = "pxc.activity_deleted"
