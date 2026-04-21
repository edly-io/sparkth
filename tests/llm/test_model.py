"""Tests for LLMConfig SQLModel."""

from app.models.llm import LLMConfig


def test_llm_config_defaults() -> None:
    config = LLMConfig(
        user_id=1,
        name="My Claude Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
    )
    assert config.is_active is True
    assert config.last_used_at is None
    assert config.id is None


def test_llm_config_table_name() -> None:
    assert LLMConfig.__tablename__ == "llm_configs"
