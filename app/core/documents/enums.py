"""Ingestion lifecycle states for a registered document."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
