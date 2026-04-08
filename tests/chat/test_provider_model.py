"""
Unit tests for the provider/model feature:
  - PROVIDER_MODELS registry and catalog helpers (providers.py)
  - ChatUserConfig.provider validation and model field (config.py)
  - _streaming_error_message error mapping (routes.py)
  - GET /api/v1/chat/providers endpoint (routes.py)
"""

from unittest.mock import MagicMock

import anthropic
import httpx
import openai
import pytest
from google.api_core import exceptions as google_exceptions

from app.core_plugins.chat.providers import (
    DEFAULT_MODEL,
    PROVIDER_MODELS,
    PROVIDER_REGISTRY,
    get_models_for_provider,
    get_provider,
    get_provider_catalog,
    get_supported_providers,
)
from app.core_plugins.chat.routes import _streaming_error_message


def _anthropic_response(status_code: int) -> httpx.Response:
    """Minimal httpx.Response for constructing Anthropic error instances."""
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
    )


def _openai_response(status_code: int) -> httpx.Response:
    """Minimal httpx.Response for constructing OpenAI error instances."""
    return httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )


# ===========================================================================
# Provider model registry
# ===========================================================================


class TestProviderModels:
    def test_all_registered_providers_have_model_list(self) -> None:
        for provider in PROVIDER_REGISTRY:
            assert provider in PROVIDER_MODELS, f"No models defined for provider '{provider}'"

    def test_each_provider_has_at_least_one_model(self) -> None:
        for provider, models in PROVIDER_MODELS.items():
            assert len(models) > 0, f"Provider '{provider}' has an empty model list"

    def test_all_model_ids_are_non_empty_strings(self) -> None:
        for provider, models in PROVIDER_MODELS.items():
            for model in models:
                assert isinstance(model, str) and model.strip(), (
                    f"Provider '{provider}' has a blank/non-string model id: {model!r}"
                )

    def test_get_models_for_known_providers(self) -> None:
        for provider in ("openai", "anthropic", "google"):
            models = get_models_for_provider(provider)
            assert isinstance(models, list)
            assert len(models) > 0

    def test_get_models_case_insensitive(self) -> None:
        assert get_models_for_provider("Anthropic") == get_models_for_provider("anthropic")
        assert get_models_for_provider("OPENAI") == get_models_for_provider("openai")

    def test_get_models_unknown_provider_returns_empty_list(self) -> None:
        assert get_models_for_provider("nonexistent") == []
        assert get_models_for_provider("") == []

    def test_get_provider_catalog_length_matches_registry(self) -> None:
        catalog = get_provider_catalog()
        assert len(catalog) == len(PROVIDER_REGISTRY)

    def test_get_provider_catalog_entry_shape(self) -> None:
        for entry in get_provider_catalog():
            assert "id" in entry
            assert "label" in entry
            assert "models" in entry
            assert isinstance(entry["id"], str) and entry["id"]
            assert isinstance(entry["label"], str) and entry["label"]
            assert isinstance(entry["models"], list) and len(entry["models"]) > 0

    def test_get_provider_catalog_ids_match_supported_providers(self) -> None:
        supported = set(get_supported_providers())
        catalog_ids = {entry["id"] for entry in get_provider_catalog()}
        assert catalog_ids == supported

    def test_get_provider_catalog_label_is_capitalised_id(self) -> None:
        for entry in get_provider_catalog():
            assert entry["label"] == entry["id"].capitalize()


# ===========================================================================
# ChatUserConfig validation
# ===========================================================================


class TestChatUserConfig:
    """
    ChatUserConfig lives in app.core_plugins.chat.config.
    We import it lazily inside each test because the module graph has a
    circular dependency that only resolves when the full app is loaded
    (which pytest's conftest initialises for us).
    """

    def test_valid_config_accepted(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        cfg = ChatUserConfig(provider="anthropic", provider_api_key_ref=1, model="claude-opus-4-5")
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-opus-4-5"

    def test_provider_is_normalised_to_lowercase(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        cfg = ChatUserConfig(provider="Anthropic", provider_api_key_ref=1, model="claude-sonnet-4-5")
        assert cfg.provider == "anthropic"

    def test_all_supported_providers_are_accepted(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        for provider in get_supported_providers():
            cfg = ChatUserConfig(
                provider=provider,
                provider_api_key_ref=1,
                model=PROVIDER_MODELS[provider][0],
            )
            assert cfg.provider == provider

    def test_invalid_provider_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError, match="Unsupported provider"):
            ChatUserConfig(provider="badprovider", provider_api_key_ref=1, model="gpt-4o")

    def test_model_defaults_to_claude_sonnet(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        cfg = ChatUserConfig(provider="anthropic", provider_api_key_ref=1)
        assert cfg.model == DEFAULT_MODEL

    def test_model_can_be_set_explicitly(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        cfg = ChatUserConfig(provider="openai", provider_api_key_ref=5, model="gpt-4o-mini")
        assert cfg.model == "gpt-4o-mini"

    def test_missing_provider_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError):
            ChatUserConfig(provider_api_key_ref=1, model="gpt-4o")  # type: ignore[call-arg]

    def test_missing_provider_api_key_ref_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError):
            ChatUserConfig(provider="openai", model="gpt-4o")  # type: ignore[call-arg]

    def test_model_from_wrong_provider_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError, match="not available for provider"):
            ChatUserConfig(provider="openai", provider_api_key_ref=1, model="claude-opus-4-5")

    def test_openai_model_rejected_for_anthropic_provider(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError, match="not available for provider"):
            ChatUserConfig(provider="anthropic", provider_api_key_ref=1, model="gpt-4o")

    def test_error_message_names_invalid_model_and_provider(self) -> None:
        from pydantic import ValidationError

        from app.core_plugins.chat.config import ChatUserConfig

        with pytest.raises(ValidationError) as exc_info:
            ChatUserConfig(provider="google", provider_api_key_ref=1, model="gpt-4o-mini")

        errors = exc_info.value.errors()
        assert any("gpt-4o-mini" in str(e) for e in errors)
        assert any("google" in str(e) for e in errors)

    def test_every_model_is_valid_for_its_own_provider(self) -> None:
        from app.core_plugins.chat.config import ChatUserConfig

        for provider, models in PROVIDER_MODELS.items():
            for model in models:
                cfg = ChatUserConfig(provider=provider, provider_api_key_ref=1, model=model)
                assert cfg.model == model


# ===========================================================================
# _streaming_error_message
# ===========================================================================


class TestStreamingErrorMessage:
    def test_anthropic_auth_error(self) -> None:
        exc = anthropic.AuthenticationError("invalid x-api-key", response=_anthropic_response(401), body=None)
        msg = _streaming_error_message(exc)
        assert "Invalid API key" in msg
        assert "Anthropic" in msg

    def test_anthropic_permission_error(self) -> None:
        exc = anthropic.PermissionDeniedError("forbidden", response=_anthropic_response(403), body=None)
        msg = _streaming_error_message(exc)
        assert "permission" in msg.lower()

    def test_anthropic_rate_limit_error(self) -> None:
        exc = anthropic.RateLimitError("rate limit exceeded", response=_anthropic_response(429), body=None)
        msg = _streaming_error_message(exc)
        assert "rate limit" in msg.lower()
        assert "Anthropic" in msg

    def test_anthropic_bad_request_error(self) -> None:
        exc = anthropic.BadRequestError("invalid request", response=_anthropic_response(400), body=None)
        msg = _streaming_error_message(exc)
        assert "rejected" in msg.lower()

    def test_anthropic_generic_api_status_error(self) -> None:
        exc = anthropic.APIStatusError("server error", response=_anthropic_response(500), body=None)
        msg = _streaming_error_message(exc)
        assert "500" in msg
        assert "Anthropic" in msg

    def test_anthropic_connection_error(self) -> None:
        exc = anthropic.APIConnectionError(
            message="connection failed",
            request=httpx.Request("POST", "https://api.anthropic.com/"),
        )
        msg = _streaming_error_message(exc)
        assert "network" in msg.lower() or "reach" in msg.lower()

    def test_openai_auth_error(self) -> None:
        exc = openai.AuthenticationError("invalid api key", response=_openai_response(401), body={})
        msg = _streaming_error_message(exc)
        assert "Invalid API key" in msg
        assert "OpenAI" in msg

    def test_openai_permission_error(self) -> None:
        exc = openai.PermissionDeniedError("forbidden", response=_openai_response(403), body={})
        msg = _streaming_error_message(exc)
        assert "permission" in msg.lower()

    def test_openai_rate_limit_error(self) -> None:
        exc = openai.RateLimitError("rate limit exceeded", response=_openai_response(429), body={})
        msg = _streaming_error_message(exc)
        assert "rate limit" in msg.lower()
        assert "OpenAI" in msg

    def test_openai_bad_request_error(self) -> None:
        exc = openai.BadRequestError("invalid request", response=_openai_response(400), body={})
        msg = _streaming_error_message(exc)
        assert "rejected" in msg.lower()

    def test_openai_generic_api_status_error(self) -> None:
        exc = openai.APIStatusError("server error", response=_openai_response(500), body={})
        msg = _streaming_error_message(exc)
        assert "500" in msg
        assert "OpenAI" in msg

    def test_openai_connection_error(self) -> None:
        exc = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/"))
        msg = _streaming_error_message(exc)
        assert "network" in msg.lower() or "reach" in msg.lower()

    def test_google_unauthenticated_error(self) -> None:
        exc = google_exceptions.Unauthenticated("invalid api key")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "Invalid API key" in msg
        assert "Google" in msg

    def test_google_permission_denied_error(self) -> None:
        exc = google_exceptions.PermissionDenied("forbidden")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "permission" in msg.lower()
        assert "Google" in msg

    def test_google_resource_exhausted_error(self) -> None:
        exc = google_exceptions.ResourceExhausted("quota exceeded")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "rate limit" in msg.lower()
        assert "Google" in msg

    def test_google_invalid_argument_error(self) -> None:
        exc = google_exceptions.InvalidArgument("bad request")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "rejected" in msg.lower()
        assert "Google" in msg

    def test_google_service_unavailable_error(self) -> None:
        exc = google_exceptions.ServiceUnavailable("unavailable")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "network" in msg.lower() or "reach" in msg.lower()
        assert "Google" in msg

    def test_google_generic_api_call_error(self) -> None:
        exc = google_exceptions.GoogleAPICallError("server error")  # type: ignore[no-untyped-call]
        msg = _streaming_error_message(exc)
        assert "Google" in msg
        assert str(exc.grpc_status_code or "unknown") in msg

    def test_runtime_error_returns_generic_message(self) -> None:
        msg = _streaming_error_message(RuntimeError("boom"))
        assert "error occurred" in msg.lower()

    def test_value_error_returns_generic_message(self) -> None:
        msg = _streaming_error_message(ValueError("bad value"))
        assert "error occurred" in msg.lower()

    def test_httpx_remote_protocol_error(self) -> None:
        exc = httpx.RemoteProtocolError("peer closed connection without sending complete message body")
        msg = _streaming_error_message(exc)
        assert "connection was interrupted" in msg.lower()
        assert "try again" in msg.lower()

    def test_all_messages_are_non_empty_strings(self) -> None:
        errors: list[Exception] = [
            anthropic.AuthenticationError("x", response=_anthropic_response(401), body=None),
            anthropic.RateLimitError("x", response=_anthropic_response(429), body=None),
            openai.AuthenticationError("x", response=_openai_response(401), body={}),
            openai.RateLimitError("x", response=_openai_response(429), body={}),
            google_exceptions.Unauthenticated("x"),  # type: ignore[no-untyped-call]
            google_exceptions.ResourceExhausted("x"),  # type: ignore[no-untyped-call]
            google_exceptions.GoogleAPICallError("x"),  # type: ignore[no-untyped-call]
            RuntimeError("x"),
        ]
        for exc in errors:
            msg = _streaming_error_message(exc)
            assert isinstance(msg, str) and msg.strip(), f"Empty message for {type(exc).__name__}"


# ===========================================================================
# GET /api/v1/chat/providers endpoint
# ===========================================================================


class TestListProvidersEndpoint:
    async def test_returns_200_for_authenticated_user(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.get("/api/v1/chat/providers")
        assert response.status_code == 200

    async def test_response_contains_providers_list(self, client: "httpx.AsyncClient", current_user: MagicMock) -> None:
        response = await client.get("/api/v1/chat/providers")
        body = response.json()
        assert "providers" in body
        assert isinstance(body["providers"], list)

    async def test_provider_count_matches_registry(self, client: "httpx.AsyncClient", current_user: MagicMock) -> None:
        response = await client.get("/api/v1/chat/providers")
        providers = response.json()["providers"]
        assert len(providers) == len(PROVIDER_REGISTRY)

    async def test_each_provider_entry_has_required_keys(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.get("/api/v1/chat/providers")
        for entry in response.json()["providers"]:
            assert "id" in entry
            assert "label" in entry
            assert "models" in entry

    async def test_each_provider_has_non_empty_models_list(
        self, client: "httpx.AsyncClient", current_user: MagicMock
    ) -> None:
        response = await client.get("/api/v1/chat/providers")
        for entry in response.json()["providers"]:
            assert isinstance(entry["models"], list)
            assert len(entry["models"]) > 0

    async def test_all_known_provider_ids_present(self, client: "httpx.AsyncClient", current_user: MagicMock) -> None:
        response = await client.get("/api/v1/chat/providers")
        ids = {entry["id"] for entry in response.json()["providers"]}
        assert ids == set(get_supported_providers())

    async def test_unauthenticated_request_is_rejected(self, client: "httpx.AsyncClient") -> None:
        response = await client.get("/api/v1/chat/providers")
        assert response.status_code in (401, 403)


# ===========================================================================
# max_retries forwarding
# ===========================================================================


class TestMaxRetriesForwarding:
    def test_max_retries_forwarded_to_openai_llm(self) -> None:
        provider = get_provider("openai", api_key="test-key", model="gpt-4o", max_retries=5)
        llm = provider._create_llm()
        assert llm.max_retries == 5

    def test_max_retries_forwarded_to_anthropic_llm(self) -> None:
        provider = get_provider("anthropic", api_key="test-key", model="claude-sonnet-4-20250514", max_retries=3)
        llm = provider._create_llm()
        assert llm.max_retries == 3

    def test_max_retries_forwarded_to_google_llm(self) -> None:
        provider = get_provider("google", api_key="test-key", model="gemini-2.0-flash", max_retries=4)
        llm = provider._create_llm()
        assert llm.max_retries == 4

    def test_max_retries_defaults_to_two(self) -> None:
        provider = get_provider("openai", api_key="test-key", model="gpt-4o")
        assert provider.max_retries == 2
        llm = provider._create_llm()
        assert llm.max_retries == 2
