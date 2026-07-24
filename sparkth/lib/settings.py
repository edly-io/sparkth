"""Application settings public API for Sparkth.

The single public entry point for application settings. All modules — application
code and plugins alike — must access settings via :func:`get_settings`, never by
importing from ``sparkth.core.config`` directly.

A plugin defining its own ``BaseSettings`` class must pass :data:`ENV_FILES` as
its ``env_file`` so it reads the same env files, in the same precedence order,
as the core ``Settings`` class.

Example:
    ```python
    from sparkth.lib.settings import get_settings

    settings = get_settings()
    print(settings.SECRET_KEY)
    ```
"""

from sparkth.core.config import ENV_FILES, get_settings

__all__ = ["ENV_FILES", "get_settings"]
