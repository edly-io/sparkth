"""Enumerations for audit events."""

from enum import StrEnum


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
