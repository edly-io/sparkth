"""Resolution of the user's preferred language.

The allowlist, the platform default and the membership check all live in
:mod:`sparkth.core.config`; this module turns a stored preference into the tag
that actually applies. Import it through the :mod:`sparkth.lib.language` façade,
never directly.
"""

from sparkth.core.config import get_settings, is_supported_language


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
