"""Tests for Accept-Language negotiation and the locale-seeding ASGI middleware."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from sparkth.core.i18n import get_locale
from sparkth.core.i18n.middleware import LocaleMiddleware, negotiate_locale


def test_negotiation_picks_a_supported_tag() -> None:
    assert negotiate_locale("es") == "es"


def test_negotiation_takes_listing_order_as_preference_order() -> None:
    assert negotiate_locale("fr,es") == "fr"


def test_negotiation_falls_through_unsupported_tags_to_a_supported_one() -> None:
    # The classic browser header: the exact-match rule rejects "en-US" but the
    # next entry still lands on "en".
    assert negotiate_locale("en-US,en;q=0.9") == "en"


def test_negotiation_discards_entry_parameters() -> None:
    assert negotiate_locale("es;q=0.1") == "es"
    assert negotiate_locale("de,es;q=0") == "es"


def test_negotiation_is_exact_and_case_sensitive() -> None:
    assert negotiate_locale("EN") is None
    assert negotiate_locale("en-US") is None


def test_negotiation_returns_none_when_nothing_is_supported() -> None:
    assert negotiate_locale("de,ja;q=0.9") is None


def test_negotiation_handles_an_empty_header() -> None:
    assert negotiate_locale("") is None


def test_negotiation_skips_the_wildcard() -> None:
    assert negotiate_locale("*") is None
    assert negotiate_locale("*,es;q=0.5") == "es"


@pytest.fixture
def locale_app() -> FastAPI:
    """A minimal app whose one route reports the locale the middleware seeded."""
    application = FastAPI()
    application.add_middleware(LocaleMiddleware)

    @application.get("/locale")
    async def read_locale() -> dict[str, str]:
        return {"locale": get_locale()}

    return application


async def _request_locale(application: FastAPI, headers: dict[str, str]) -> str:
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        response = await client.get("/locale", headers=headers)
    assert response.status_code == 200
    locale: str = response.json()["locale"]
    return locale


async def test_middleware_seeds_the_locale_from_accept_language(locale_app: FastAPI) -> None:
    assert await _request_locale(locale_app, {"Accept-Language": "es"}) == "es"


async def test_middleware_falls_back_to_the_default_without_a_header(locale_app: FastAPI) -> None:
    assert await _request_locale(locale_app, {}) == "en"


async def test_middleware_falls_back_when_no_offered_tag_is_supported(locale_app: FastAPI) -> None:
    assert await _request_locale(locale_app, {"Accept-Language": "de"}) == "en"
