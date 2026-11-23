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


class ResponseGenerationStatus(StrEnum):
    """Where a streamed reply's writing stands."""

    GENERATING = "generating"
    SKIPPING_RAG = "skipping_rag"


class DocumentProcessingStatus(StrEnum):
    """What a streamed reply does with the author's files."""

    SEARCHING_DOCUMENTS = "searching_documents"
    SCANNING_ATTACHMENTS = "scanning_attachments"


class DocumentSectionProcessingStatus(StrEnum):
    """What a streamed reply does with a document section."""

    SCANNING_SECTION = "scanning_section"
    SECTION_CONFIRMED = "section_confirmed"


class ToolExecutionStatus(StrEnum):
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
