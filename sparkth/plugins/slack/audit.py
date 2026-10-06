"""Audit event types owned by the Slack plugin.

The Slack workspace credential lifecycle: a user installing the bot into a
workspace, and removing it. Snapshots carry the Slack ``team_id`` and
``bot_user_id`` only, never the bot token.
"""

from dataclasses import dataclass
from typing import ClassVar

from sparkth.lib.audit.events import MutationAuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS

SLACK_WORKSPACE_TARGET = "slack_workspace"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class SlackConnectedAuditEvent(MutationAuditEvent):
    """A user completed the Slack OAuth flow and the workspace was stored."""

    event_type: ClassVar[str] = "slack.connected"


@AUDIT_EVENTS.register
@dataclass(frozen=True, slots=True, kw_only=True)
class SlackDisconnectedAuditEvent(MutationAuditEvent):
    """A user disconnected their Slack workspace (soft-deleted)."""

    event_type: ClassVar[str] = "slack.disconnected"
