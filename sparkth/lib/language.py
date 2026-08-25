"""Public API for language resolution and language naming.

The single entry point for the supported-language allowlist, for checking whether a
language tag belongs to it, and for naming an arbitrary language tag for a prompt.
Application code and plugins import from here, never from ``sparkth.core.language`` or
``sparkth.core.config``.

Example:
    ```python
    from sparkth.lib.language import is_supported_language, language_display_name

    if current_user.language and is_supported_language(current_user.language):
        ...   # membership check, e.g. before binding
    name = language_display_name("pt-BR")   # "Portuguese (Brazil)", for a prompt
    ```
"""

from sparkth.core.config import SUPPORTED_LANGUAGES, LanguageInfo, is_supported_language
from sparkth.core.language import language_display_name, resolve_language

__all__ = [
    "SUPPORTED_LANGUAGES",
    "LanguageInfo",
    "is_supported_language",
    "language_display_name",
    "resolve_language",
]
