"""Enumerations for audit events."""

from enum import StrEnum


class AuditActorType(StrEnum):
    """Kind of actor behind an event (the NIST AU-3 who field).

    USER: an authenticated, known identity. The action is attributed to a
    real account, so ``id`` is the user's database ID and ``label`` their
    username.

    ANONYMOUS: someone acted, but we don't know (or can't trust) who they
    are. The canonical case is a failed login: the caller typed a username,
    but since they failed authentication the event cannot be attributed to
    that account's identity. The actor carries no identity fields at all; the
    claimed username is recorded on the event's target as untrusted evidence.

    SYSTEM: no human behind the action, the platform itself did it
    (scheduled jobs, background tasks, CLI maintenance commands, automated
    cleanup).

    The taxonomy is closed: unlike event types, plugins must not invent new
    actor kinds. Each value has a dedicated actor class in
    :mod:`sparkth.core.audit.context`; the classes fix ``type`` per kind and
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
