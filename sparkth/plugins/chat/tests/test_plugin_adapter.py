"""Tests for ChatConfigAdapter registration."""

from sparkth.lib.config import get_plugin_adapter
from sparkth.lib.llm import LLMConfigAdapter
from sparkth.plugins.chat.adapter import ChatConfigAdapter


def test_chat_adapter_extends_llm_config_adapter() -> None:
    assert issubclass(ChatConfigAdapter, LLMConfigAdapter)


def test_chat_adapter_registered_in_config_adapters() -> None:
    adapter = get_plugin_adapter("chat")
    assert isinstance(adapter, ChatConfigAdapter)
