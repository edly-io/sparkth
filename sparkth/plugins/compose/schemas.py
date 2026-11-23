import base64
import binascii
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from sparkth.plugins.compose.constants import MAX_COMBINED_UPLOAD_MB
from sparkth.plugins.compose.enums import (
    DocumentProcessingStatus,
    DocumentSectionProcessingStatus,
    ResponseGenerationStatus,
    ToolExecutionStatus,
)
from sparkth.plugins.compose.models import MessageRole, MessageType
from sparkth.plugins.compose.planner.types import PlanSnapshot

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str | list[dict[str, Any]] = Field(...)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed_roles = {"system", "user", "assistant", "tool"}
        if v not in allowed_roles:
            raise ValueError(f"Invalid role: {v}. Allowed: {', '.join(allowed_roles)}")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Content must not be empty")
        if isinstance(v, list) and len(v) == 0:
            raise ValueError("Content must not be empty")
        if isinstance(v, list):
            for block in v:
                if not isinstance(block, dict):
                    continue
                source = block.get("source")
                if isinstance(source, dict) and source.get("type") == "base64":
                    data = source.get("data", "")
                    try:
                        size = len(base64.b64decode(data))
                    except binascii.Error:
                        raise ValueError("Invalid base64 data in content block")
                    if size > MAX_FILE_SIZE:
                        raise ValueError("File size exceeds 30MB limit")
                if block.get("type") == "drive_file":
                    document_id = block.get("file_id")
                    if not isinstance(document_id, int) or document_id <= 0:
                        raise ValueError("legacy document content block must have a positive integer 'file_id'")
        return v


class UploadedFile(BaseModel):
    """A file uploaded from the computer, as the text read from it."""

    name: str = Field(max_length=255)
    # A file with more text than a conversation may keep can never be accepted.
    text: str = Field(max_length=MAX_COMBINED_UPLOAD_MB * 1024 * 1024)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ChatCompletionRequest(BaseModel):
    llm_config_id: int = Field(..., description="ID of the LLMConfig to use for this completion")
    model_override: str | None = Field(
        default=None,
        description="Overrides the model in the selected LLMConfig",
    )
    messages: list[ChatMessage] = Field(..., min_length=1)
    conversation_id: UUID | None = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)
    stream: bool = Field(default=False)
    tools: list[str] | str | None = Field(
        default="*",
        description="Includes every tool of the plugins the requesting user has switched on and has permission to use. "
        "Use 'none' or empty list to disable.",
    )
    document_ids: list[int] | None = Field(
        default=None,
        max_length=20,
        description=(
            "Document IDs to attach to the conversation before processing "
            "(used when attaching documents on a new conversation)."
        ),
    )
    turn_id: UUID | None = Field(
        default=None,
        description="Client-generated id for this turn, used to stop it while it streams.",
    )
    files: list[UploadedFile] = Field(
        default_factory=list,
        description="The files uploaded from the computer with this turn. Kept for later turns, never in the database.",
    )

    @field_validator("messages")
    @classmethod
    def validate_a_user_turn_is_present(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        """A completion answers something a user sent, so one user turn is the minimum.

        Downstream the last user message is what gets answered, judged for scope and retrieved
        against. Without one there is nothing to answer, and every reader of it would need
        behaviour for a turn that does not exist. An attachment-only turn qualifies: what is
        absent there is the text, not the request.
        """
        if not any(message.role == "user" for message in v):
            raise ValueError("messages must include at least one user message")
        return v


class ChatCompletionResponse(BaseModel):
    message: ChatMessage
    conversation_id: UUID | None = None
    model: str
    provider: str
    tokens_used: int | None = None
    cost: float | None = None
    tool_calls: list[ToolCall] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSection(BaseModel):
    type: str
    name: str
    source: str | None = None


class StreamStatusEvent(BaseModel):
    """A status event of a streamed reply: what Compose is doing before or between the reply's text."""

    done: Literal[False] = False


class ResponseGenerationEvent(StreamStatusEvent):
    """Compose starts writing the reply, or answers without searching documents."""

    status: ResponseGenerationStatus


class DocumentProcessingEvent(StreamStatusEvent):
    """Compose searches the author's documents or scans their attachments, ``file_count`` files."""

    status: DocumentProcessingStatus
    file_count: int


class DocumentSectionProcessingEvent(StreamStatusEvent):
    """Compose scans a document section, or confirms it for the reply."""

    status: DocumentSectionProcessingStatus
    section: RagSection


class StepEvent(StreamStatusEvent):
    """A step starts; ``step_status`` is what the author reads while it works."""

    status: Literal["step"] = "step"
    step_status: str


class PlanEvent(StreamStatusEvent):
    """The plan is shown, or its running step moves."""

    status: Literal["plan"] = "plan"
    plan: PlanSnapshot


class ToolExecutionEvent(StreamStatusEvent):
    """A tool call starts or ends."""

    status: Literal["tool_call"] = "tool_call"
    tool_name: str
    tool_status: ToolExecutionStatus


class PersistedToolCall(BaseModel):
    name: str


class MessageResponse(BaseModel):
    id: int
    role: MessageRole
    content: str
    tokens_used: int | None
    cost: float | None
    created_at: datetime
    message_type: MessageType
    attachment_name: str | None
    attachment_size: int | None
    rag_sections: list[RagSection] | None = None
    tool_calls: list[PersistedToolCall] | None = None
    plan: PlanSnapshot | None = None
    is_error: bool = False
    stopped: bool = False


class ConversationResponse(BaseModel):
    id: UUID
    provider: str
    model: str
    title: str | None
    total_tokens_used: int
    total_cost: float
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]


class ClassifierVerdict(BaseModel):
    """What every classifier verdict carries besides its decision.

    A negative decision is the one a user or a reviewer asks about later, and the decision
    itself does not say why. The reason is written by the model and read from a log, which is
    why it is specified as a category rather than free narration: the message being judged can
    hold course content, and these logs have never carried any of it.
    """

    refusal_reason: str = Field(
        default="",
        description=(
            "When the decision is negative, a short phrase naming the category it fell under. "
            "Name the category only: never quote or restate the user's message. Leave empty "
            "when the decision is positive."
        ),
    )


class DocumentHeadings(BaseModel):
    """One attached document as the search classifier sees it: a name and its section paths.

    ``structure_unavailable`` separates headings that could not be read from a document that
    genuinely has none; both arrive with empty ``sections``.
    """

    name: str
    sections: list[str] = Field(default_factory=list)
    structure_unavailable: bool = False


class RAGSearchInput(BaseModel):
    """What the search classifier is asked to judge: a message against what the documents hold."""

    query: str
    documents: list[DocumentHeadings] = Field(default_factory=list)


class RAGSearchVerdict(ClassifierVerdict):
    """Whether answering this message needs content retrieved from the attached documents."""

    requires_search: bool


class ConversationAttachmentCreate(BaseModel):
    """Request body for attaching a document to a conversation."""

    document_id: int


class ConversationAttachmentResponse(BaseModel):
    """Response for a conversation attachment."""

    id: int
    conversation_id: int
    document_id: int
    attached_at: datetime


class AttachedDocumentResponse(BaseModel):
    """Document info returned by the list-attachments endpoint."""

    id: int
    name: str
    size: int | None
    # The id of the source the document came from, or None when that isn't recorded.
    source: str | None


class UploadedFileResponse(BaseModel):
    """A file uploaded from the computer that a conversation still has, without its text."""

    name: str
    # The length of the file's text, which is what counts toward the conversation's upload limit.
    size: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolListResponse(BaseModel):
    tools: list[ToolSchema]
    total: int
