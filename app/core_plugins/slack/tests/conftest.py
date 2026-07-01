"""Shared fixtures for Slack plugin tests."""

import os

# Slack OAuth credentials default to "" in core config, so they are optional for
# app boot. Set test values before importing app modules so settings-reading
# tests see them. This env is plugin-local — it stays out of the shared
# app.testing module.
os.environ.setdefault("SLACK_CLIENT_ID", "test-slack-client-id")
os.environ.setdefault("SLACK_CLIENT_SECRET", "test-slack-client-secret")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-slack-signing-secret")
os.environ.setdefault("SLACK_REDIRECT_URI", "http://localhost:7727/api/v1/slack/callback")

from collections.abc import AsyncGenerator, Generator
from typing import Any, cast
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.slack.config import SlackSettings
from app.core_plugins.slack.models import SlackWorkspace
from app.core_plugins.slack.service import encrypt_token
from app.lib.auth import get_current_user
from app.lib.settings import get_settings
from app.main import app
from app.models.user import User


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    user = User(
        name="Slack Test User",
        username="slackuser",
        email="slack@example.com",
        hashed_password="fakehashedpassword",
    )
    session.add(user)
    # Commit (not just flush) so handlers running on their own engine-backed session
    # see the seeded row and don't roll it back when their session_scope closes.
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_workspace(session: AsyncSession, test_user: User) -> SlackWorkspace:
    workspace = SlackWorkspace(
        user_id=cast(int, test_user.id),
        team_id="T123ABC",
        team_name="Test Workspace",
        bot_token_encrypted=encrypt_token("xoxb-fake-bot-token"),
        bot_user_id="U_BOT_ID",
        is_active=True,
    )
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


@pytest.fixture
def mock_slack_credentials() -> Generator[None, None, None]:
    fake = SlackSettings(
        client_id="fake_client_id",
        client_secret="fake_client_secret",
        redirect_uri="http://localhost/callback",
        signing_secret="fake_signing_secret",
    )
    with patch(
        "app.core_plugins.slack.routes.oauth.get_slack_credentials",
        return_value=fake,
    ):
        yield


@pytest.fixture
async def slack_client(
    session: AsyncSession,
    test_user: User,
    mock_slack_credentials: Any,
) -> AsyncGenerator[AsyncClient, None]:
    # No get_async_session override: handlers open their own engine-backed session on
    # the same in-memory StaticPool DB as the `session` fixture. Only auth is faked.
    async def get_user_override() -> User:
        return test_user

    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_current_user, None)
