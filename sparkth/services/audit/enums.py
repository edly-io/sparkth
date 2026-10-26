"""Enums for reading the audit trail."""

from enum import StrEnum


class ExportFormat(StrEnum):
    """Machine-readable shapes an export can stream as."""

    CSV = "csv"
    JSONL = "jsonl"
