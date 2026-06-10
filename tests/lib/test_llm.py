"""Tests for the app.lib.llm public API surface.

Everything here is imported from app.lib.llm only — this suite exercises the
public boundary, never the LLM internals behind it.
"""

import pytest

import app.lib.llm as llm_api
from app.lib.llm import (
    BaseChatProvider,
    LLMConfigAdapter,
    LLMConfigDuplicateNameError,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigService,
    LLMConfigValidationError,
    get_llm_service,
    get_provider,
)


class TestLLMPublicApi:
    def test_exposes_provider_base_and_factory(self) -> None:
        assert isinstance(BaseChatProvider, type)
        assert callable(llm_api.get_provider)

    def test_exposes_service_and_factory(self) -> None:
        assert isinstance(LLMConfigService, type)
        assert callable(llm_api.get_llm_service)

    def test_exposes_adapter(self) -> None:
        assert isinstance(LLMConfigAdapter, type)

    def test_exposes_config_exceptions(self) -> None:
        for exc in (
            LLMConfigDuplicateNameError,
            LLMConfigInactiveError,
            LLMConfigModelNotSetError,
            LLMConfigNotFoundError,
            LLMConfigValidationError,
        ):
            assert issubclass(exc, ValueError)


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
