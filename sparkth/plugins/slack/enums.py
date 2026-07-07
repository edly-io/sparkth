"""Enumerations for the Slack TA Bot plugin."""

from enum import Enum


class ResponseType(str, Enum):
    RAG_MATCH = "rag_match"
    FALLBACK = "fallback"
    GREETING = "greeting"
    CONFIG_INCOMPLETE = "config_incomplete"
    PLUGIN_DISABLED = "plugin_disabled"
    LEGACY = "legacy"
    NO_FILES_RESOLVED = "no_files_resolved"
    RAG_NOT_READY = "rag_not_ready"
    DRIVE_FILE_NOT_FOUND = "drive_file_not_found"
    RETRIEVAL_ERROR = "retrieval_error"


class ConnectionEventType(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
