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

# How much of a rejected tag is worth writing down. 35 is the practical ceiling for a
# registered BCP 47 tag — the bound ``User.language`` and the MCP request field carry — so
# anything past it cannot be a tag someone meant. Bounded here as well as at those edges
# because this is public API (``sparkth.lib.language``): a future caller need not have a
# field validator in front of it, and one of today's callers is unauthenticated.
_MAX_LOGGED_TAG_LENGTH = 35


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
            # The exception's own message quotes the input straight back, so logging it
            # would write the tag a second time. Its class is the only part that says
            # anything the tag does not: unparseable versus parseable-but-unknown.
            logger.warning(
                "Unusable language tag %r (%s), falling back",
                candidate[:_MAX_LOGGED_TAG_LENGTH],
                type(exc).__name__,
            )
            continue
        if name:
            return name
        logger.warning(
            "Language tag %r has no English display name, falling back",
            candidate[:_MAX_LOGGED_TAG_LENGTH],
        )
    return default
