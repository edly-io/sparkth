import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.models.whitelist import WhitelistedEmail


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _whitelist(session: AsyncSession, email: str) -> None:
    session.add(WhitelistedEmail(value=email.lower(), entry_type="email", added_by_id=None))
    await session.flush()


@pytest.fixture(autouse=True)
def enable_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "REGISTRATION_ENABLED", True)


class TestRegisterSendsVerificationEmail:
    async def test_creates_unverified_user_and_sends_email(self, client: AsyncClient, session: AsyncSession) -> None:
        email = f"{_uniq('new')}@example.com"
        await _whitelist(session, email)
        await session.commit()

        with patch(
            "app.api.v1.auth.send_verification_email",
            new_callable=AsyncMock,
        ) as mock_send:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Alice",
                    "username": _uniq("alice"),
                    "email": email,
                    "password": "Sup3rSecret!",
                },
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == email
        assert body["email_verified"] is False

        user_result = await session.exec(select(User).where(User.email == email))
        created = user_result.one()
        token_result = await session.exec(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == created.id)
        )
        assert token_result.one_or_none() is not None

        mock_send.assert_awaited_once()
        assert mock_send.await_args is not None
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to"] == email
        assert kwargs["name"] == "Alice"
        assert isinstance(kwargs["raw_token"], str)

    async def test_email_is_normalized_to_lowercase(self, client: AsyncClient, session: AsyncSession) -> None:
        """Mixed-case email at registration should be stored lowercased so the
        resend lookup (which lowercases) finds the user."""
        mixed = f"{_uniq('mixed')}@Example.COM"
        await _whitelist(session, mixed.lower())
        await session.commit()

        with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Mixed",
                    "username": _uniq("mixed"),
                    "email": mixed,
                    "password": "Sup3rSecret!",
                },
            )

        assert response.status_code == 200
        result = await session.exec(select(User).where(User.email == mixed.lower()))
        assert result.one_or_none() is not None


class TestLoginBlocksUnverified:
    async def test_unverified_returns_403_with_code(self, client: AsyncClient, session: AsyncSession) -> None:
        username = _uniq("u")
        email = f"{username}@example.com"
        user = User(
            name="Bob",
            username=username,
            email=email,
            hashed_password=security.get_password_hash("Sup3rSecret!"),
            email_verified=False,
        )
        session.add(user)
        await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Sup3rSecret!"},
        )

        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["code"] == "email_not_verified"
        assert detail["email"] == email

    async def test_verified_can_login(self, client: AsyncClient, session: AsyncSession) -> None:
        username = _uniq("u")
        user = User(
            name="Carol",
            username=username,
            email=f"{username}@example.com",
            hashed_password=security.get_password_hash("Sup3rSecret!"),
            email_verified=True,
        )
        session.add(user)
        await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Sup3rSecret!"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestVerifyEmailEndpoint:
    async def test_happy_path_marks_user_verified(self, client: AsyncClient, session: AsyncSession) -> None:
        from app.services.email_verification import EmailVerificationService

        username = _uniq("u")
        user = User(
            name="Dee",
            username=username,
            email=f"{username}@example.com",
            hashed_password="x",
            email_verified=False,
        )
        session.add(user)
        await session.flush()
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)
        await session.commit()

        response = await client.post("/api/v1/auth/verify-email", json={"token": raw})
        assert response.status_code == 200
        assert response.json()["email_verified"] is True

    async def test_invalid_token_returns_400(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/verify-email", json={"token": "bogus"})
        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_token"

    async def test_expired_token_returns_400(self, client: AsyncClient, session: AsyncSession) -> None:
        from datetime import datetime, timezone

        from app.services.email_verification import EmailVerificationService

        username = _uniq("u")
        user = User(
            name="Eve",
            username=username,
            email=f"{username}@example.com",
            hashed_password="x",
            email_verified=False,
        )
        session.add(user)
        await session.flush()
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)

        token_row = (
            await session.exec(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
        ).one()
        token_row.expires_at = datetime.now(timezone.utc).replace(year=2000)
        session.add(token_row)
        await session.commit()

        response = await client.post("/api/v1/auth/verify-email", json={"token": raw})
        assert response.status_code == 400
        assert response.json()["detail"] == "expired_token"

    async def test_used_token_returns_400(self, client: AsyncClient, session: AsyncSession) -> None:
        from app.services.email_verification import EmailVerificationService

        username = _uniq("u")
        user = User(
            name="Frank",
            username=username,
            email=f"{username}@example.com",
            hashed_password="x",
            email_verified=False,
        )
        session.add(user)
        await session.flush()
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)
        await session.commit()

        ok = await client.post("/api/v1/auth/verify-email", json={"token": raw})
        assert ok.status_code == 200

        again = await client.post("/api/v1/auth/verify-email", json={"token": raw})
        assert again.status_code == 400
        assert again.json()["detail"] == "invalid_token"


class TestResendEndpoint:
    @pytest.fixture(autouse=True)
    def fake_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Replace the rate-limit Redis with an in-memory shim."""
        from app.api.v1 import auth as auth_module

        store: dict[str, str] = {}

        class FakeRedis:
            async def set(
                self,
                key: str,
                value: str,
                ex: int | None = None,
                nx: bool = False,
            ) -> bool | None:
                if nx and key in store:
                    return None
                store[key] = value
                return True

            async def aclose(self) -> None:
                """Match the real client's lifecycle so the endpoint's finally clause works."""

        async def get_fake_redis() -> FakeRedis:
            return FakeRedis()

        monkeypatch.setattr(auth_module, "_get_resend_redis", get_fake_redis)

    async def test_unknown_email_returns_202(self, client: AsyncClient) -> None:
        with patch(
            "app.api.v1.auth.send_verification_email",
            new_callable=AsyncMock,
        ) as mock_send:
            response = await client.post(
                "/api/v1/auth/verify-email/resend",
                json={"email": "ghost@example.com"},
            )
        assert response.status_code == 202
        mock_send.assert_not_awaited()

    async def test_already_verified_returns_202_no_send(self, client: AsyncClient, session: AsyncSession) -> None:
        username = _uniq("u")
        user = User(
            name="Greta",
            username=username,
            email=f"{username}@example.com",
            hashed_password="x",
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        with patch(
            "app.api.v1.auth.send_verification_email",
            new_callable=AsyncMock,
        ) as mock_send:
            response = await client.post(
                "/api/v1/auth/verify-email/resend",
                json={"email": user.email},
            )
        assert response.status_code == 202
        mock_send.assert_not_awaited()

    async def test_unverified_sends_email(self, client: AsyncClient, session: AsyncSession) -> None:
        username = _uniq("u")
        email = f"{username}@example.com"
        user = User(
            name="Hank",
            username=username,
            email=email,
            hashed_password="x",
            email_verified=False,
        )
        session.add(user)
        await session.flush()

        with patch(
            "app.api.v1.auth.send_verification_email",
            new_callable=AsyncMock,
        ) as mock_send:
            response = await client.post(
                "/api/v1/auth/verify-email/resend",
                json={"email": email},
            )
        assert response.status_code == 202
        mock_send.assert_awaited_once()
        assert mock_send.await_args is not None
        assert mock_send.await_args.kwargs["to"] == email

    async def test_rate_limit_returns_429(self, client: AsyncClient, session: AsyncSession) -> None:
        username = _uniq("u")
        email = f"{username}@example.com"
        user = User(
            name="Iris",
            username=username,
            email=email,
            hashed_password="x",
            email_verified=False,
        )
        session.add(user)
        await session.flush()

        with patch("app.api.v1.auth.send_verification_email", new_callable=AsyncMock):
            first = await client.post(
                "/api/v1/auth/verify-email/resend",
                json={"email": email},
            )
            second = await client.post(
                "/api/v1/auth/verify-email/resend",
                json={"email": email},
            )

        assert first.status_code == 202
        assert second.status_code == 429
        assert second.json()["detail"] == "rate_limited"
