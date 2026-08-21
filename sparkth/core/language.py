"""Resolution of the user's preferred language, and naming of arbitrary language tags.

The allowlist, the platform default and the membership check all live in
:mod:`sparkth.core.config`; this module turns a stored preference into the tag
that actually applies, and names any BCP 47 tag for a prompt. Import it through
the :mod:`sparkth.lib.language` façade, never directly.
"""

from babel import Locale
from babel.core import UnknownLocaleError

from sparkth.core.config import get_settings, is_supported_language
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


def resolve_language(tag: str | None) -> str:
    """The language a stored preference of ``tag`` resolves to.

    ``tag`` is a user's stored choice, or ``None`` when they never made one.
    Returns it when it is still supported, and otherwise ``DEFAULT_LANGUAGE`` —
    which covers both cases where the stored value cannot be honoured: the user
    never chose, and the tag has since left the allowlist. A language withdrawn
    from the list (say, because its output quality was poor) must stop being
    handed back for the users who had already picked it.
    """
    if tag and is_supported_language(tag):
        return tag
    return get_settings().DEFAULT_LANGUAGE


def language_display_name(tag: str | None) -> str:
    """The English name of the language ``tag`` identifies.

    ``tag`` is an arbitrary BCP 47 tag supplied by a caller — it is deliberately not
    checked against :data:`SUPPORTED_LANGUAGES`, which governs the interface
    translations the platform ships rather than the languages the model may write in.
    ``"de"`` therefore yields ``"German"`` even though no German interface exists.

    Falls back to the platform default's name when ``tag`` is absent, is not a
    parseable language tag, or parses to a locale with no English display name in
    CLDR (e.g. ``"skr"``, Saraiki) — so a misspelled or obscure value degrades to the
    default instead of failing the caller's whole request or surfacing the literal
    string ``"None"``. Babel's parser defaults to the POSIX underscore separator, so
    the BCP 47 hyphen is passed explicitly.
    """
    default = get_settings().DEFAULT_LANGUAGE
    for candidate in (tag, default):
        if not candidate:
            continue
        try:
            name = Locale.parse(candidate, sep="-").get_display_name("en")
        except (UnknownLocaleError, ValueError) as exc:
            logger.info("Unusable language tag %r, falling back: %s", candidate, exc)
            continue
        if name:
            return name
        logger.info("Language tag %r has no English display name, falling back", candidate)
    return default
