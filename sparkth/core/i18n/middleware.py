"""ASGI middleware that seeds the per-request locale from ``Accept-Language``."""

from starlette.types import ASGIApp, Receive, Scope, Send

from sparkth.core.config import is_supported_language
from sparkth.core.i18n.context import locale_context


def negotiate_locale(header: str) -> str | None:
    """Pick the first supported tag from an ``Accept-Language`` value.

    Entries are taken in listing order, with anything after a ``;`` discarded:
    browsers list languages by descending preference, so the order alone
    carries the preference. Matching is exact and case-sensitive, the same
    rule as :func:`sparkth.core.config.is_supported_language`: ``en-US`` does
    not match ``en``, but a browser sending ``en-US,en`` still lands on ``en``
    through its next entry. Returns None when nothing offered is supported, so
    the caller falls back to ``DEFAULT_LANGUAGE``.
    """
    for entry in header.split(","):
        tag = entry.partition(";")[0].strip()
        if is_supported_language(tag):
            return tag
    return None


class LocaleMiddleware:
    """Seed the request locale negotiated from the ``Accept-Language`` header.

    Pure ASGI (no BaseHTTPMiddleware) so it adds no response buffering. When
    the header is absent or offers no supported tag the contextvar stays unset
    and :func:`~sparkth.core.i18n.context.get_locale` serves
    ``DEFAULT_LANGUAGE``. The header is only what is knowable at the edge: this
    middleware runs before authentication, so it cannot see a signed-in user.
    ``User.language`` is bound later, by the authentication dependency — the first point
    in the request at which the locale is bound to that stored preference.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        locale: str | None = None
        for key, value in scope["headers"]:
            if key == b"accept-language":
                locale = negotiate_locale(value.decode("latin-1"))
                break
        if locale is None:
            await self.app(scope, receive, send)
            return
        with locale_context(locale):
            await self.app(scope, receive, send)
