"""Self-service account domain exceptions (HTTP-agnostic).

These are plain ``Exception`` subclasses: they never carry an HTTP status. The API layer
(``sparkth/api/v1/user/__init__.py``) maps each concrete subclass to a status via
``register_exception_handler``.
"""

__all__ = [
    "AccountError",
    "IncorrectPassword",
    "PasswordNotSet",
]


class AccountError(Exception):
    """Base class for self-service account errors."""


class IncorrectPassword(AccountError):
    """The current password the user typed does not match the stored one."""


class PasswordNotSet(AccountError):
    """The account has no password to change: the user signs in with Google only."""
