"""Tests for persistent document attachment on conversations."""

from app.core_plugins.chat.routes import _extract_drive_file_id_from_messages
from app.core_plugins.chat.schemas import ChatMessage, ConversationResponse


def _user_msg(content: str | list[dict[str, object]]) -> ChatMessage:
    return ChatMessage(role="user", content=content)


class TestExtractDriveFileId:
    def test_extracts_drive_file_id_from_content_blocks(self) -> None:
        messages = [_user_msg([{"type": "drive_file", "file_id": 42}, {"type": "text", "text": "hello"}])]
        assert _extract_drive_file_id_from_messages(messages) == 42

    def test_returns_none_for_plain_text_messages(self) -> None:
        messages = [_user_msg("Just text")]
        assert _extract_drive_file_id_from_messages(messages) is None

    def test_returns_none_for_no_drive_file_blocks(self) -> None:
        messages = [_user_msg([{"type": "text", "text": "hello"}])]
        assert _extract_drive_file_id_from_messages(messages) is None

    def test_returns_first_drive_file_id(self) -> None:
        messages = [_user_msg([{"type": "drive_file", "file_id": 10}, {"type": "drive_file", "file_id": 20}])]
        assert _extract_drive_file_id_from_messages(messages) == 10


class TestConversationResponseSchema:
    def test_includes_active_drive_file_fields(self) -> None:
        from datetime import datetime
        from uuid import UUID

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
            active_drive_file_id=42,
            active_drive_file_name="doc.pdf",
        )
        assert resp.active_drive_file_id == 42
        assert resp.active_drive_file_name == "doc.pdf"

    def test_defaults_to_none(self) -> None:
        from datetime import datetime
        from uuid import UUID

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
        assert resp.active_drive_file_id is None
        assert resp.active_drive_file_name is None
