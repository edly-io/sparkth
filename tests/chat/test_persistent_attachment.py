"""Tests for conversation response schema."""

from datetime import datetime
from uuid import UUID

from app.core_plugins.chat.schemas import ConversationResponse


class TestConversationResponseSchema:
    def test_conversation_response_required_fields(self) -> None:
        resp = ConversationResponse(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            provider="openai",
            model="gpt-4",
            title="Test",
            total_tokens_used=0,
            total_cost=0.0,
            message_count=0,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        assert resp.provider == "openai"
        assert resp.model == "gpt-4"
