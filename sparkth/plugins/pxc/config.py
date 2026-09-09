"""Environment-backed settings for the PXC plugin.

Only ``PXC_``-prefixed variables belong here, read through the same env files and in the same
precedence order as the core ``Settings`` class — which is what ``sparkth.lib.settings``
requires of a plugin that defines its own settings, and what makes a value set in ``.env`` or
``.env.local`` actually reach this plugin.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from sparkth.lib.settings import ENV_FILES


class PxcSettings(BaseSettings):
    """The PXC plugin's configuration, one field per ``PXC_`` environment variable."""

    model_config = SettingsConfigDict(
        env_prefix="PXC_",
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Where the per-activity-type SQLite state files and the activities' file storage live.
    # One file per activity type holds every course and every learner for that type (D1).
    data_dir: Path = Path("./data/pxc")

    # Shared with the Open edX XBlock. The XBlock signs a launch token with it and this plugin
    # verifies that signature, which is what makes the learner's identity trustworthy rather
    # than client-asserted. Sensitive: set it in .env.local, never in .env. Empty fails closed.
    launch_secret: str = ""

    # How long a launch token stays valid. Short: it is minted per page render.
    launch_token_ttl_seconds: int = 300

    # The activity type published by the "pxc" contributor. One bundled sample is served for
    # every request by design (L5); an authoring module chooses per placement later.
    default_activity: str = "mcq"


@lru_cache
def get_pxc_settings() -> PxcSettings:
    """The PXC plugin's settings, read once per process."""
    return PxcSettings()
