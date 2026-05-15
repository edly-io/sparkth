import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB


class AttachmentMeta(BaseModel):
    name: str
    size: int


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str | list[dict[str, Any]] = Field(...)
    attachment: AttachmentMeta | None = None

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
                    file_id = block.get("file_id")
                    if not isinstance(file_id, int) or file_id <= 0:
                        raise ValueError("drive_file content block must have a positive integer 'file_id'")
        return v


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str


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
        default="*", description="Automatically includes all tools. Use 'none' or empty list to disable."
    )
    tool_choice: str | None = Field(
        default="auto", description="How to use tools: 'auto', 'none', or specific tool name"
    )
    include_system_tools_message: bool = Field(
        default=True, description="Automatically prepend a system message listing available tools"
    )
    similarity_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Cosine similarity threshold for RAG chunk retrieval (0 = very loose, 1 = exact match)",
    )
    drive_file_ids: list[int] | None = Field(
        default=None,
        max_length=20,
        description="Drive file IDs to attach to the conversation before processing (used when attaching files on a new conversation).",
    )


class ChatCompletionResponse(BaseModel):
    message: ChatMessage
    conversation_id: UUID
    model: str
    provider: str
    tokens_used: int | None = None
    cost: float | None = None
    tool_calls: list[ToolCall] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    provider: str
    model: str
    title: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = Field(default=None)


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    tokens_used: int | None
    cost: float | None
    created_at: datetime
    message_type: str
    attachment_name: str | None
    attachment_size: int | None
    rag_sections: list[dict[str, Any]] | None = None
    is_error: bool = False


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


class RAGRoutingDecision(BaseModel):
    """Decision from RAG intent router on whether to run retrieval for this turn."""

    should_retrieve: bool
    reason: str


class ConversationAttachmentCreate(BaseModel):
    """Request body for attaching a drive file to a conversation."""

    drive_file_id: int


class ConversationAttachmentResponse(BaseModel):
    """Response for a conversation attachment."""

    id: int
    conversation_id: int
    drive_file_id: int
    attached_at: datetime


class AttachedDriveFileResponse(BaseModel):
    """Drive file info returned by the list-attachments endpoint."""

    id: int
    name: str
    size: int | None


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


class ErrorResponse(BaseModel):
    detail: str
    error_code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    id: str
    label: str
    models: list[str]


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderInfo]
    default_provider: str
    default_model: str
