"""Enumerations for the Slack TA Bot plugin."""

from enum import Enum


class ResponseType(str, Enum):
    rag_match = "rag_match"
    fallback = "fallback"
    greeting = "greeting"
    config_incomplete = "config_incomplete"
    plugin_disabled = "plugin_disabled"
    legacy = "legacy"
    no_files_resolved = "no_files_resolved"
    rag_not_ready = "rag_not_ready"
    drive_file_not_found = "drive_file_not_found"
    retrieval_error = "retrieval_error"


class ConnectionEventType(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
