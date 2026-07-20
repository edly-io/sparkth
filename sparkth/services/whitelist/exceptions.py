"""Whitelist domain exceptions (HTTP-agnostic).

This module was generated with LLM (Claude) assistance.

These are plain ``Exception`` subclasses — they never carry an HTTP status. The API layer
(``sparkth/api/v1/whitelist/__init__.py``) maps each concrete subclass to a status via
``register_exception_handler``.
"""

__all__ = [
    "WhitelistError",
    "InvalidWhitelistValue",
    "WhitelistEntryAlreadyExists",
    "WhitelistEntryNotFound",
]


class WhitelistError(Exception):
    """Base class for whitelist domain errors."""


class InvalidWhitelistValue(WhitelistError):
    """The value is neither a valid email address nor a valid domain."""


class WhitelistEntryAlreadyExists(WhitelistError):
    """A whitelist entry with this value already exists."""


class WhitelistEntryNotFound(WhitelistError):
    """No whitelist entry exists for the given id."""
