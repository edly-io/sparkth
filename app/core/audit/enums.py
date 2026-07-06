"""Enumerations for audit events."""

from enum import StrEnum


class AuditActorType(StrEnum):
    """Kind of actor behind an event (the NIST AU-3 who field).

    The taxonomy is closed: unlike event types, plugins must not invent new
    actor kinds. Each value has a dedicated actor class in
    :mod:`app.core.audit.context`; the classes fix ``type`` per kind and
    enforce the per-kind field invariants at construction.
    """

    USER = "user"
    SYSTEM = "system"
    ANONYMOUS = "anonymous"


class AuditOutcome(StrEnum):
    """How the audited action ended (the NIST AU-3 outcome field)."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditSource(StrEnum):
    """Which surface produced the event (the NIST AU-3 where/source field)."""

    REST = "rest"
    MCP = "mcp"
    CHAT = "chat"
    RAG = "rag"
    CLI = "cli"
    SYSTEM = "system"
