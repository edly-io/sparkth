"""Tests for the sparkth.lib.llm public API surface.

Everything here is imported from sparkth.lib.llm only — this suite exercises the
public boundary, never the LLM internals behind it.
"""

import pytest

from sparkth.lib.llm import BaseChatProvider, LLMConfigService, get_llm_service, get_provider


class TestGetProvider:
    def test_returns_base_chat_provider_instance(self) -> None:
        provider = get_provider("anthropic", api_key="k", model="claude-sonnet-4-5")
        assert isinstance(provider, BaseChatProvider)

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(ValueError):
            get_provider("nope", api_key="k", model="m")


class TestGetLLMService:
    def test_returns_service_instance(self) -> None:
        assert isinstance(get_llm_service(), LLMConfigService)
