"""Enums shared across the compose plugin."""

from enum import StrEnum


class PlannerModel(StrEnum):
    """Which model the planner runs on."""

    SMALL = "small"
    SAME_AS_COMPOSE = "same_as_compose"


class OptionsFence(StrEnum):
    """The tag of the fenced block that offers the author choices."""

    MULTIPLE = "options"
    SINGLE = "options single"


class TurnEventType(StrEnum):
    """What one event of a running turn reports."""

    ROUTED = "routed"
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    LIMIT_REACHED = "limit_reached"
    USAGE = "usage"
    FINAL = "final"
