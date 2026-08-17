"""Public API for the user's preferred language.

The single entry point for the supported-language allowlist and for language
resolution. Application code and plugins import from here, never from
``sparkth.core.language`` or ``sparkth.core.config``.

Example:
    ```python
    from sparkth.lib.language import resolve_language

    language = resolve_language(current_user.language)
    ```
"""

from sparkth.core.config import SUPPORTED_LANGUAGES, LanguageInfo, is_supported_language
from sparkth.core.language import resolve_language

__all__ = [
    "SUPPORTED_LANGUAGES",
    "LanguageInfo",
    "is_supported_language",
    "resolve_language",
]
