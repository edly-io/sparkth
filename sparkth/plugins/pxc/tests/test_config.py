"""The PXC plugin's environment-backed settings."""

import pytest

from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcInvalidLaunchToken
from sparkth.plugins.pxc.tokens import mint_launch_token, read_launch_token


def test_the_pxc_prefix_maps_onto_the_settings_field_names(monkeypatch: pytest.MonkeyPatch) -> None:
    # The prefix mapping is the whole contract with the env files: rename a field and it
    # silently stops reading its variable, falling back to a default with nothing logged.
    monkeypatch.setenv("PXC_DATA_DIR", "/tmp/pxc-somewhere-else")
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "from-the-environment")
    monkeypatch.setenv("PXC_LAUNCH_TOKEN_TTL_SECONDS", "42")
    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", "/opt/somewhere/toolchain")
    monkeypatch.setenv("PXC_BUILD_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("PXC_BUILD_CONCURRENCY", "3")
    monkeypatch.setenv("PXC_BUILD_ERROR_LIMIT", "11")
    monkeypatch.setenv("PXC_BUILD_STDERR_LIMIT_BYTES", "12")
    monkeypatch.setenv("PXC_MAX_SOURCE_CHARS", "13")
    monkeypatch.setenv("PXC_MAX_DESCRIPTION_CHARS", "14")
    monkeypatch.setenv("PXC_LIST_ACTIVITIES_LIMIT", "15")
    get_pxc_settings.cache_clear()

    settings = get_pxc_settings()

    assert str(settings.data_dir) == "/tmp/pxc-somewhere-else"
    assert settings.launch_secret == "from-the-environment"
    assert settings.launch_token_ttl_seconds == 42
    assert str(settings.toolchain_dir) == "/opt/somewhere/toolchain"
    assert settings.build_timeout_seconds == 7
    assert settings.build_concurrency == 3
    assert settings.build_error_limit == 11
    assert settings.build_stderr_limit_bytes == 12
    assert settings.max_source_chars == 13
    assert settings.max_description_chars == 14
    assert settings.list_activities_limit == 15


def test_only_pxc_prefixed_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # The plugin's settings are its own: an unprefixed variable of the same name belongs to
    # something else and must not bleed in.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "the-pxc-one")
    monkeypatch.setenv("LAUNCH_SECRET", "not-the-pxc-one")
    get_pxc_settings.cache_clear()

    assert get_pxc_settings().launch_secret == "the-pxc-one"


def test_a_secret_from_configuration_is_what_verifies_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # A secret set only in .env.local has to reach verification. Nothing in the process exports
    # these variables — pydantic-settings reads the env files itself — so a secret resolved any
    # other way leaves verification unconfigured and refuses every launch with a 401.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "configured-in-env-local-not-exported")
    get_pxc_settings.cache_clear()

    token = mint_launch_token(
        "mcq", "instance-1", "course-1", "learner-7", "play", "configured-in-env-local-not-exported", 300
    )

    assert read_launch_token(token).activity == "mcq"


def test_the_token_ttl_default_comes_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # The TTL has to be resolved per call, not frozen at import: a value captured when the
    # module loads ignores whatever is configured for the process that imports it. A negative
    # lifetime is the cheapest way to observe that the configured value is the one actually
    # applied — zero would expire exactly now, and the expiry check is strict.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "a-secret-of-at-least-32-bytes-long")
    monkeypatch.setenv("PXC_LAUNCH_TOKEN_TTL_SECONDS", "-10")
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcInvalidLaunchToken, match="[Ee]xpired"):
        read_launch_token(mint_launch_token("mcq", "p", "c", "u", "play", "a-secret-of-at-least-32-bytes-long"))
