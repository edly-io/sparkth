"""Static-translation (i18n) core: the request locale and gettext catalogs.

The locale travels in a contextvar, seeded per request by
:class:`~sparkth.core.i18n.middleware.LocaleMiddleware` from the
``Accept-Language`` header (validated against the ``SUPPORTED_LANGUAGES``
allowlist in :mod:`sparkth.core.config`), so deep call sites translate without
threading a request object through every layer — the same shape as the audit
context. Outside any request the platform ``DEFAULT_LANGUAGE`` applies.

Application code and plugins import this via :mod:`sparkth.lib.i18n`, never
from here directly.
"""

from sparkth.core.i18n.context import get_locale, locale_context
from sparkth.core.i18n.translate import LazyString, gettext, gettext_noop, lazy_gettext

__all__ = ["LazyString", "get_locale", "gettext", "gettext_noop", "lazy_gettext", "locale_context"]
