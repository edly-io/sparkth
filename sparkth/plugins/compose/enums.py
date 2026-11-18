"""Enums shared across the compose plugin."""

from enum import StrEnum


class PlannerModel(StrEnum):
    """Which model the planner runs on."""

    SMALL = "small"
    SAME_AS_COMPOSE = "same_as_compose"


class OptionsFence(StrEnum):
    """The tag of the fenced block that offers the author choices."""

    MANY = "options"
    SINGLE = "options single"


class StreamStatus(StrEnum):
    """What a status event of a streamed reply reports."""

    SCANNING_ATTACHMENTS = "scanning_attachments"
    SEARCHING_DOCUMENTS = "searching_documents"
    SKIPPING_RAG = "skipping_rag"
    SECTION_SCANNING = "section_scanning"
    SECTION_CONFIRMED = "section_confirmed"
    GENERATING = "generating"
    STEP = "step"
    TOOL_CALL = "tool_call"


class ToolCallStatus(StrEnum):
    """Where a tool call reported on a streamed reply stands."""

    RUNNING = "running"
    DONE = "done"


class TurnEventType(StrEnum):
    """What one event of a running turn reports."""

    ROUTED = "routed"
    PLAN = "plan"
    PLAN_STEP = "plan_step"
    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    LIMIT_REACHED = "limit_reached"
    USAGE = "usage"
    FINAL = "final"
