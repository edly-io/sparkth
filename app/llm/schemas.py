"""Pydantic request/response schemas for LLMConfig endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.llm.providers import get_models_for_provider, get_supported_providers


class LLMConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., examples=["anthropic"])
    model: str = Field(..., examples=["claude-sonnet-4-20250514"])
    api_key: str = Field(..., min_length=1, max_length=500)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        supported = get_supported_providers()
        if v.lower() not in supported:
            raise ValueError(f"Unsupported provider '{v}'. Supported: {', '.join(supported)}")
        return v.lower()

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str, info: ValidationInfo) -> str:
        provider = info.data.get("provider")
        if provider:
            allowed = get_models_for_provider(provider)
            if v not in allowed:
                raise ValueError(f"Model '{v}' not available for provider '{provider}'. Allowed: {', '.join(allowed)}")
        return v


class LLMConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=100)


class LLMConfigRotateKey(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=500)


class LLMConfigSetActive(BaseModel):
    is_active: bool


class LLMConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    model: str
    masked_key: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class LLMConfigListResponse(BaseModel):
    configs: list[LLMConfigResponse]
    total: int
