"""Static-translation (i18n) public API for Sparkth.

The single public entry point for translating user-facing strings. All modules
— application code and plugins alike — must import the marking functions from
here, never from ``sparkth.core.i18n`` directly.

How to mark a string:

- Inside request handling, wrap the literal in :func:`gettext`, imported as
  ``_``::

      from sparkth.lib.i18n import _

      raise HTTPException(status_code=401, detail=_("Incorrect username or password"))

- f-strings cannot be extracted by ``pybabel``; convert them to
  ``str.format`` on the translated template::

      _("Role not found: {role_name}").format(role_name=role_name)

- Module-level constants evaluate at import, before any request locale
  exists; mark them with :func:`lazy_gettext` and render with ``str()`` at
  the boundary::

      from sparkth.lib.i18n import lazy_gettext

      GREETING_MESSAGE = lazy_gettext("Hello! How can I help you?")

- A constant stored in a plain-``str`` field (a dataclass a response model
  embeds, where a :class:`LazyString` cannot go): mark the literal with
  :func:`gettext_noop` at the definition and translate the stored value by
  passing it through :func:`gettext` where it is rendered::

      DisplayInfo(gettext_noop("Create Course"), gettext_noop("Build courses with AI"))

Extraction and catalogs are driven by the ``i18n.*`` Make targets (see
``make help``). Core's catalogs live in ``sparkth/locale``; a plugin ships its
own by registering its catalog directory on the :data:`LOCALE_DIRS` hook from
its ``__init__``::

    from pathlib import Path

    from sparkth.lib.i18n import LOCALE_DIRS

    LOCALE_DIRS.add_item(Path(__file__).parent / "locale")

The locale itself is negotiated per request from ``Accept-Language`` by the
locale middleware and read via :func:`get_locale`. The allowlist that
negotiation matches against, and the resolution of a user's stored preference,
belong to :mod:`sparkth.lib.language`; this module covers translation only.
"""

from sparkth.core.i18n import LazyString, bind_locale, get_locale, gettext, gettext_noop, lazy_gettext
from sparkth.core.i18n.hooks import LOCALE_DIRS

# The conventional alias pybabel's default keywords pick up at call sites.
_ = gettext

__all__ = [
    "LOCALE_DIRS",
    "LazyString",
    "_",
    "bind_locale",
    "get_locale",
    "gettext",
    "gettext_noop",
    "lazy_gettext",
]
