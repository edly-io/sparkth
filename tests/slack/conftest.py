"""Shared fixtures for Slack plugin tests."""

from collections.abc import AsyncGenerator, Generator
from typing import Any, cast
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.core.db import get_session
from app.core_plugins.slack.models import SlackWorkspace
from app.main import app
from app.models.user import User

# Register Slack routes once (mirrors the googledrive pattern)
_SLACK_PREFIX = "/api/v1/slack"
_slack_routes_registered = False


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ensure_slack_routes() -> None:
    global _slack_routes_registered
    if _slack_routes_registered:
        return
    try:
        from app.core_plugins.slack.routes import router as slack_router

        existing = {getattr(r, "path", None) for r in app.routes}
        if f"{_SLACK_PREFIX}/oauth/authorize" not in existing:
            app.include_router(slack_router, prefix=_SLACK_PREFIX, tags=["Slack TA Bot"])
        _slack_routes_registered = True
    except ImportError:
        pass  # routes not yet implemented; model/config tests still run


_ensure_slack_routes()


@pytest.fixture
def test_user(sync_session: Session) -> User:
    user = User(
        name="Slack Test User",
        username="slackuser",
        email="slack@example.com",
        hashed_password="fakehashedpassword",
    )
    sync_session.add(user)
    sync_session.commit()
    sync_session.refresh(user)
    return user


@pytest.fixture
def test_workspace(sync_session: Session, test_user: User) -> SlackWorkspace:
    from app.core_plugins.slack.oauth import encrypt_token

    workspace = SlackWorkspace(
        user_id=cast(int, test_user.id),
        team_id="T123ABC",
        team_name="Test Workspace",
        bot_token_encrypted=encrypt_token("xoxb-fake-bot-token"),
        bot_user_id="U_BOT_ID",
        is_active=True,
    )
    sync_session.add(workspace)
    sync_session.commit()
    sync_session.refresh(workspace)
    return workspace


@pytest.fixture
def mock_slack_credentials() -> Generator[None, None, None]:
    with patch(
        "app.core_plugins.slack.routes.get_slack_credentials",
        return_value=(
            "fake_client_id",
            "fake_client_secret",
            "http://localhost/callback",
            "fake_signing_secret",
        ),
    ):
        yield


@pytest.fixture
async def slack_client(
    sync_session: Session,
    test_user: User,
    mock_slack_credentials: Any,
) -> AsyncGenerator[AsyncClient, None]:
    def get_session_override() -> Generator[Session, None, None]:
        yield sync_session

    async def get_user_override() -> User:
        return test_user

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
