import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

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
