"""Enums shared across the compose plugin."""

from enum import StrEnum


class TurnEventType(StrEnum):
    """What one event of a running turn reports."""

    ROUTED = "routed"
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    LIMIT_REACHED = "limit_reached"
    USAGE = "usage"
    FINAL = "final"
