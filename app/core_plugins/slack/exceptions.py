class SlackSignatureError(Exception):
    """Raised when a Slack request signature cannot be verified."""


class WorkspaceAlreadyConnectedError(Exception):
    """Raised when a Slack workspace is already connected to a different user account."""


class UserAlreadyConnectedError(Exception):
    """Raised when a user already has an active Slack workspace connection.
    Disconnect first before connecting a new one."""
