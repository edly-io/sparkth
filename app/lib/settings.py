"""Application settings public API for Sparkth.

The single public entry point for application settings. All modules — application
code and plugins alike — must access settings via :func:`get_settings`, never by
importing from ``app.core.config`` directly.

Example:
    ```python
    from app.lib.settings import get_settings

    settings = get_settings()
    print(settings.SECRET_KEY)
    ```
"""

from app.core.config import get_settings as get_settings
