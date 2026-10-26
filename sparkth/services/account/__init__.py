"""Self-service account package: changes a user makes to their own account, signed in or
through an emailed password reset link."""

from sparkth.services.account.exceptions import (
    AccountError,
    IncorrectPassword,
    PasswordNotSet,
    ResetLinkExpired,
    ResetLinkInvalid,
)
from sparkth.services.account.password_reset import (
    ResetEmail,
    request_password_reset,
    reset_password,
    send_password_reset_email,
)
from sparkth.services.account.service import change_password

__all__ = [
    "change_password",
    "request_password_reset",
    "reset_password",
    "send_password_reset_email",
    "AccountError",
    "IncorrectPassword",
    "PasswordNotSet",
    "ResetEmail",
    "ResetLinkExpired",
    "ResetLinkInvalid",
]
