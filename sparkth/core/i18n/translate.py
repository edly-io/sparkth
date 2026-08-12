"""gettext-backed message catalogs and the string-marking functions.

Marking rules:

- A literal evaluated during a request: wrap it in :func:`gettext` (imported
  as ``_``) at the point of use.
- An f-string: convert to :func:`gettext` + ``str.format`` —
  ``_("Role not found: {role_name}").format(role_name=role_name)`` — because
  ``pybabel extract`` cannot see inside f-strings.
- A module-level constant: wrap it in :func:`lazy_gettext`, which defers
  translation to render time (module bodies run at import, before any request
  locale exists).

Catalogs are compiled ``.mo`` files under the directories registered on the
:data:`~sparkth.core.i18n.hooks.LOCALE_DIRS` hook — core's ``sparkth/locale``
(registered below, produced by ``make i18n.compile``) plus any directory a
plugin registers. Every registered directory is consulted; the source language
(English) needs no catalog because a missing catalog or message falls back to
the source string.
"""

import gettext as gettext_module
from functools import lru_cache
from pathlib import Path

from sparkth.core.i18n.context import get_locale
from sparkth.core.i18n.hooks import LOCALE_DIRS

# Core's own catalog directory, sparkth/locale.
LOCALE_DIR: Path = Path(__file__).resolve().parents[2] / "locale"

LOCALE_DIRS.add_item(LOCALE_DIR)

_DOMAIN = "messages"


@lru_cache(maxsize=None)
def _load_catalogs(locale: str, locale_dirs: tuple[Path, ...]) -> gettext_module.NullTranslations:
    """Chain the compiled catalogs of every registered directory for ``locale``.

    ``gettext`` fallbacks cascade: a lookup misses through the chain and
    finally returns the source message, which is exactly the behaviour the
    source language and catalog-less directories need (``fallback=True``).
    """
    chain = gettext_module.NullTranslations()
    for locale_dir in locale_dirs:
        chain.add_fallback(gettext_module.translation(_DOMAIN, locale_dir, languages=[locale], fallback=True))
    return chain


def gettext(message: str) -> str:
    """Translate ``message`` into the active request locale.

    The canonical marker for user-facing strings; import it as ``_`` so
    ``pybabel extract`` picks the call sites up.
    """
    return _load_catalogs(get_locale(), tuple(LOCALE_DIRS.iter_values())).gettext(message)


class LazyString:
    """A translation deferred to render time.

    Module-level constants evaluate at import, before any request locale
    exists; wrapping them keeps the marking at the definition site while the
    translation happens when the value is rendered. The object is not a
    ``str`` — call ``str()`` on it at the boundary (response serialization,
    message dispatch).
    """

    __slots__ = ("_message",)

    def __init__(self, message: str) -> None:
        self._message = message

    def __str__(self) -> str:
        return gettext(self._message)

    def __repr__(self) -> str:
        return f"LazyString({self._message!r})"


def lazy_gettext(message: str) -> LazyString:
    """Mark ``message`` for translation but defer it to render time.

    For module-level constants and other values built before a request locale
    exists. Extraction picks these up via ``pybabel extract -k lazy_gettext``.
    """
    return LazyString(message)
