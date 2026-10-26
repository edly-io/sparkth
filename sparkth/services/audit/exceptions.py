"""Audit read domain exceptions (HTTP-agnostic).

The API layer (``sparkth/api/v1/audit.py``) maps each one to a status via
``register_exception_handler``.
"""

__all__ = ["AuditEventNotFound"]


class AuditEventNotFound(Exception):
    """No audit event has the requested id."""
