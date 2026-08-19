"""A signed-in user's stored language wins over the Accept-Language header.

The locale middleware runs before authentication, so it can only negotiate the header.
Once the user is resolved, their stored choice is the better answer: they chose it, and the
browser did not.
"""

from collections.abc import Iterator

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.i18n.context import _locale, get_locale, locale_context
from sparkth.core.security import create_access_token
from sparkth.lib.auth import get_current_user
from sparkth.lib.i18n import bind_locale
from sparkth.lib.models import User
from sparkth.lib.settings import get_settings
from sparkth.lib.testing import AddTranslation

# The marked detail PATCH /api/v1/llm/configs/{config_id} raises for an empty body — the check
# runs before any database access, so it exercises get_current_user without seeding an LLMConfig.
EMPTY_BODY_MESSAGE = "Empty body. Nothing to update."
SPANISH_EMPTY_BODY = "Cuerpo vacío. Nada que actualizar."
FRENCH_EMPTY_BODY = "Corps vide. Rien à mettre à jour."


@pytest.fixture(autouse=True)
def _reset_locale() -> Iterator[None]:
    """Undo whatever ``bind_locale`` installs, since it deliberately never does.

    ``bind_locale`` is a bare ``ContextVar.set()`` with no matching ``reset()`` (see its
    docstring: there is nothing to restore within a real request, because the request's
    context is discarded with its task). A synchronous test calling it directly — unlike an
    ``async`` route test, which runs in its own task with a copied context that is thrown
    away when the task ends — mutates this thread's ambient context for good, leaking into
    every test that runs after it. This fixture snapshots and restores that ambient value
    around each test in this module so ``TestBindLocale`` can call ``bind_locale`` bare, the
    way production code does, without contaminating the rest of the suite.
    """
    token = _locale.set(_locale.get())
    yield
    _locale.reset(token)


class TestBindLocale:
    def test_replaces_a_locale_installed_by_the_middleware(self) -> None:
        with locale_context("fr"):
            bind_locale("es")
            assert get_locale() == "es"

    def test_binds_when_no_locale_is_installed(self) -> None:
        """The header may offer nothing supported, in which case the middleware installs
        no context at all — the binding must still take effect."""
        bind_locale("es")
        assert get_locale() == "es"

    def test_leaves_the_default_intact_when_never_called(self) -> None:
        assert get_locale() == get_settings().DEFAULT_LANGUAGE


def _auth_headers(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


async def _seed_user(session: AsyncSession, username: str, language: str | None) -> User:
    user = User(
        name="Locale Test",
        username=username,
        email=f"{username}@example.com",
        hashed_password="not-a-real-hash",
        language=language,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


class TestStoredPreferenceWinsOverTheHeader:
    """Drives a real request through the app with a real bearer token.

    Deliberately does not use the ``current_user`` fixture: it overrides
    ``get_current_user`` outright with a stub that unconditionally returns a fixed user, so
    the real dependency body — and the ``bind_locale`` call this task adds to it — never
    runs under that fixture. A real user row plus a real JWT against a route with no
    override is the only way to reach the binding.
    """

    async def test_stored_language_overrides_accept_language(
        self,
        client: AsyncClient,
        session: AsyncSession,
        translation_catalog: AddTranslation,
    ) -> None:
        translation_catalog(EMPTY_BODY_MESSAGE, SPANISH_EMPTY_BODY, locale="es")
        translation_catalog(EMPTY_BODY_MESSAGE, FRENCH_EMPTY_BODY, locale="fr")
        await _seed_user(session, "stored-lang-user", "es")

        response = await client.patch(
            "/api/v1/llm/configs/1",
            json={},
            headers={**_auth_headers("stored-lang-user"), "Accept-Language": "fr"},
        )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail == SPANISH_EMPTY_BODY
        assert detail != FRENCH_EMPTY_BODY

    @pytest.mark.parametrize("stored", [None, "klingon"])
    async def test_unusable_stored_language_leaves_the_header_in_charge(
        self,
        client: AsyncClient,
        session: AsyncSession,
        translation_catalog: AddTranslation,
        stored: str | None,
    ) -> None:
        """An unset preference, or one whose language has since left the allowlist, must
        not override a header the user's browser did offer."""
        translation_catalog(EMPTY_BODY_MESSAGE, FRENCH_EMPTY_BODY, locale="fr")
        await _seed_user(session, "unusable-lang-user", stored)

        response = await client.patch(
            "/api/v1/llm/configs/1",
            json={},
            headers={**_auth_headers("unusable-lang-user"), "Accept-Language": "fr"},
        )

        assert response.status_code == 422
        assert response.json()["detail"] == FRENCH_EMPTY_BODY


def _cached_request(user: User) -> Request:
    """A bare ASGI request scope carrying ``user`` the way ``PluginAccessMiddleware``
    leaves it on ``request.state`` for every authenticated plugin route, before
    ``get_current_user`` ever runs."""
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "root_path": "",
            "headers": [],
            "query_string": b"",
            "app": None,
        }
    )
    request.state.user = user
    return request


class TestCachedUserBranchBindsToo:
    """``get_current_user`` has two exits that hand back a ``User``: the cached one, taken
    when ``PluginAccessMiddleware`` already resolved the caller (every authenticated plugin
    route — chat, canvas, googledrive, open-edx, slack), and the full-lookup one exercised
    by ``TestStoredPreferenceWinsOverTheHeader`` above. Binding only on the lookup path
    would leave the stored preference unapplied on every plugin route, so this covers the
    cached path directly — no token or database row needed, since that branch reads
    neither.
    """

    async def test_binds_the_stored_language_on_the_cached_path(
        self,
        session: AsyncSession,
    ) -> None:
        user = User(
            id=1,
            name="Cached User",
            username="cacheduser",
            email="cacheduser@example.com",
            hashed_password="not-a-real-hash",
            language="es",
        )
        request = _cached_request(user)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="unused")

        result = await get_current_user(request, credentials, session)

        assert result is user
        assert get_locale() == "es"
