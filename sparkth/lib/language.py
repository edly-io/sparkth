"""Public API for language resolution and language naming.

The single entry point for the supported-language allowlist, for resolving a user's
stored interface-language preference, and for naming an arbitrary language tag for a
prompt. Application code and plugins import from here, never from
``sparkth.core.language`` or ``sparkth.core.config``.

Example:
    ```python
    from sparkth.lib.language import language_display_name, resolve_language

    locale = resolve_language(current_user.language)   # an interface locale
    name = language_display_name("pt-BR")              # "Portuguese (Brazil)"
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
