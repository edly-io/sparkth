"""Self-service account package: changes a signed-in user makes to their own account."""

from sparkth.services.account.exceptions import AccountError, IncorrectPassword, PasswordNotSet
from sparkth.services.account.service import change_password

__all__ = [
    "change_password",
    "AccountError",
    "IncorrectPassword",
    "PasswordNotSet",
]
