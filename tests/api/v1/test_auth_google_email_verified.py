import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.user import User
from app.models.whitelist import WhitelistedEmail


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def google_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(s, "REGISTRATION_ENABLED", True)


async def _whitelist(session: AsyncSession, email: str) -> None:
    session.add(WhitelistedEmail(value=email.lower(), entry_type="email", added_by_id=None))
    await session.flush()


class TestGoogleCallbackVerification:
    async def test_new_google_user_is_verified(self, client: AsyncClient, session: AsyncSession) -> None:
        email = f"{_uniq('g')}@example.com"
        await _whitelist(session, email)
        await session.commit()

        with (
            patch(
                "app.api.v1.auth.exchange_auth_code",
                new_callable=AsyncMock,
                return_value={"access_token": "fake"},
            ),
            patch(
                "app.api.v1.auth.get_google_user_info",
                new_callable=AsyncMock,
                return_value={
                    "id": _uniq("gid"),
                    "email": email,
                    "name": "Google User",
                },
            ),
        ):
            response = await client.get("/api/v1/auth/google/callback?code=x")

        assert response.status_code == 302
        result = await session.exec(select(User).where(User.email == email))
        user = result.one()
        assert user.email_verified is True
        assert user.email_verified_at is not None

    async def test_linking_google_to_unverified_user_marks_verified(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        email = f"{_uniq('g')}@example.com"
        existing = User(
            name="Existing",
            username=_uniq("u"),
            email=email,
            hashed_password="x",
            email_verified=False,
        )
        session.add(existing)
        await session.flush()

        with (
            patch(
                "app.api.v1.auth.exchange_auth_code",
                new_callable=AsyncMock,
                return_value={"access_token": "fake"},
            ),
            patch(
                "app.api.v1.auth.get_google_user_info",
                new_callable=AsyncMock,
                return_value={
                    "id": _uniq("gid"),
                    "email": email,
                    "name": "Existing",
                },
            ),
        ):
            response = await client.get("/api/v1/auth/google/callback?code=x")

        assert response.status_code == 302
        result = await session.exec(select(User).where(User.email == email))
        refreshed = result.one()
        assert refreshed.email_verified is True
        assert refreshed.email_verified_at is not None
