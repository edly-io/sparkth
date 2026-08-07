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


async def test_requires_authentication(client: AsyncClient) -> None:
    """Gated like /dashboard — no token, no list.

    Deliberately omits the ``current_user`` fixture: without it no
    ``get_current_user`` override is installed, so the real dependency runs and
    rejects the unauthenticated request.
    """
    response = await client.get("/api/v1/languages")

    assert response.status_code == 401
