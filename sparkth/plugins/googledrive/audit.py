"""Audit event types owned by the Google Drive plugin.

The Drive OAuth credential lifecycle: a user granting Sparkth access to their
Drive, and revoking it. Snapshots carry the granted scopes only, never token
material.
"""

from dataclasses import dataclass
from typing import ClassVar

from sparkth.lib.audit.events import MutationAuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS

DRIVE_CONNECTION_TARGET = "googledrive_connection"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class DriveConnectedAuditEvent(MutationAuditEvent):
    """A user completed the Drive OAuth flow and its tokens were stored.

    A reconnect that refreshes an existing record is still a connect;
    ``change.new`` carries the granted ``scopes``. Silent access-token
    refreshes are not recorded.
    """

    event_type: ClassVar[str] = "googledrive.connected"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class DriveDisconnectedAuditEvent(MutationAuditEvent):
    """A user disconnected Drive and the stored tokens were soft-deleted.

    ``change.old`` carries the ``scopes`` the connection had.
    """

    event_type: ClassVar[str] = "googledrive.disconnected"
