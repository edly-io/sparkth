"""Tests for ChatConfigAdapter registration."""

from app.core_plugins.chat.adapter import ChatConfigAdapter
from app.lib.config import get_plugin_adapter
from app.lib.llm import LLMConfigAdapter


def test_chat_adapter_extends_llm_config_adapter() -> None:
    assert issubclass(ChatConfigAdapter, LLMConfigAdapter)


def test_chat_adapter_registered_in_config_adapters() -> None:
    adapter = get_plugin_adapter("chat")
    assert isinstance(adapter, ChatConfigAdapter)
