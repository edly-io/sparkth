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
    monkeypatch.setenv("PXC_DEFAULT_ACTIVITY", "some-other-activity")
    get_pxc_settings.cache_clear()

    settings = get_pxc_settings()

    assert str(settings.data_dir) == "/tmp/pxc-somewhere-else"
    assert settings.launch_secret == "from-the-environment"
    assert settings.launch_token_ttl_seconds == 42
    assert settings.default_activity == "some-other-activity"


def test_only_pxc_prefixed_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    # The plugin's settings are its own: an unprefixed variable of the same name belongs to
    # something else and must not bleed in.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "the-pxc-one")
    monkeypatch.setenv("LAUNCH_SECRET", "not-the-pxc-one")
    get_pxc_settings.cache_clear()

    assert get_pxc_settings().launch_secret == "the-pxc-one"


def test_a_secret_from_configuration_is_what_verifies_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # The defect this module fixes: the secret was read with os.getenv at import time, which
    # the env files never populate, so a secret configured in .env.local left verification
    # permanently unconfigured and refused every launch with a 401.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "configured-not-exported")
    get_pxc_settings.cache_clear()

    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "configured-not-exported", 300)

    assert read_launch_token(token).activity == "mcq"


def test_the_token_ttl_default_comes_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # mint_launch_token used to take the TTL as an import-time default argument, which froze it
    # at whatever the environment held when the module was first imported. A negative lifetime
    # is the cheapest way to observe that the configured value is the one actually applied:
    # zero would expire exactly now, and the expiry check is strict.
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "a-secret")
    monkeypatch.setenv("PXC_LAUNCH_TOKEN_TTL_SECONDS", "-10")
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcInvalidLaunchToken, match="[Ee]xpired"):
        read_launch_token(mint_launch_token("mcq", "p", "c", "u", "a-secret"))
