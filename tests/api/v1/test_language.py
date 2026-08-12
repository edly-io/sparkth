"""Tests for the supported-languages endpoint."""

from httpx import AsyncClient

from sparkth.core.models.user import User


async def test_lists_every_supported_language(client: AsyncClient, current_user: User) -> None:
    response = await client.get("/api/v1/languages")

    assert response.status_code == 200
    codes = [language["code"] for language in response.json()["languages"]]
    assert sorted(codes) == ["en", "es", "fr"]


async def test_each_entry_carries_both_display_names(client: AsyncClient, current_user: User) -> None:
    response = await client.get("/api/v1/languages")

    spanish = next(lang for lang in response.json()["languages"] if lang["code"] == "es")
    assert spanish["name"] == "Spanish"
    assert spanish["native_name"] == "Español"


async def test_reports_the_platform_default(client: AsyncClient, current_user: User) -> None:
    response = await client.get("/api/v1/languages")

    assert response.json()["default"] == "en"


async def test_does_not_require_authentication(client: AsyncClient) -> None:
    """The login, register and password-reset pages need this list before any token exists.

    Deliberately omits the ``current_user`` fixture: without it no
    ``get_current_user`` override is installed, so a gate on this route would run
    for real and reject the request.
    """
    response = await client.get("/api/v1/languages")

    assert response.status_code == 200
    assert response.json()["default"] == "en"
