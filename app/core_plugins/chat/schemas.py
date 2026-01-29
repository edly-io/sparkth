from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProviderAPIKeyCreate(BaseModel):
    provider: str = Field(..., examples=["openai"])
    api_key: str = Field(..., min_length=1)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        from app.core_plugins.chat.providers import get_supported_providers
        
        supported = get_supported_providers()
        if v.lower() not in supported:
            raise ValueError(f"Unsupported provider: {v}. Supported: {', '.join(supported)}")
        return v.lower()


class ProviderAPIKeyResponse(BaseModel):
    id: int
    provider: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]


class ProviderAPIKeyListResponse(BaseModel):
    keys: List[ProviderAPIKeyResponse]
    total: int


class ChatMessage(BaseModel):
    role: str = Field(..., examples=["user"])
    content: str = Field(..., min_length=1)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed_roles = {"system", "user", "assistant", "tool"}
        if v not in allowed_roles:
            raise ValueError(f"Invalid role: {v}. Allowed: {', '.join(allowed_roles)}")
        return v


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str


class ChatCompletionRequest(BaseModel):
    provider: str = Field(..., examples=["openai"])
    model: str = Field(..., examples=["gpt-4", "claude-3-opus", "gemini-pro"])
    messages: List[ChatMessage] = Field(..., min_length=1)
    conversation_id: Optional[int] = Field(default=None)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    stream: bool = Field(default=False)
    tools: Optional[List[str] | str] = Field(
        default="*", 
        description="Automatically includes all tools. Use 'none' or empty list to disable."
    )
    tool_choice: Optional[str] = Field(default="auto", description="How to use tools: 'auto', 'none', or specific tool name")
    include_system_tools_message: bool = Field(
        default=True,
        description="Automatically prepend a system message listing available tools"
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        from app.core_plugins.chat.providers import get_supported_providers
        
        supported = get_supported_providers()
        if v.lower() not in supported:
            raise ValueError(f"Unsupported provider: {v}. Supported: {', '.join(supported)}")
        return v.lower()


class ChatCompletionResponse(BaseModel):
    message: ChatMessage
    conversation_id: int
    model: str
    provider: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    tool_calls: Optional[List[ToolCall]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    provider: str
    model: str
    title: Optional[str] = Field(default=None, max_length=255)
    system_prompt: Optional[str] = Field(default=None)


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    tokens_used: Optional[int]
    cost: Optional[float]
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    provider: str
    model: str
    title: Optional[str]
    total_tokens_used: int
    total_cost: float
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse]


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class ToolListResponse(BaseModel):
    tools: List[ToolSchema]
    total: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
