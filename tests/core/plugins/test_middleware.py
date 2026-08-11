"""Behavioural tests for the per-user plugin access gate (PluginAccessMiddleware).

The gate answers one question before a request reaches its route: does the caller still
have this plugin turned on? Each test drives a real request through the assembled app so
the whole chain is exercised — resolving which plugin owns the URL, resolving the caller
from the bearer token, and the access lookup itself.
"""

from typing import cast

import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.core.plugins.middleware import PluginAccessMiddleware
from sparkth.core.security import create_access_token
from sparkth.main import assemble_app

CHAT_COMPLETIONS_PATH = "/api/v1/chat/completions"
SLACK_CALLBACK_PATH = "/api/v1/slack/oauth/callback"


def _request(app: FastAPI, method: str, path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "root_path": "",
            "headers": [],
            "query_string": b"",
            "app": app,
        }
    )


def _auth_headers(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


async def _seed_user(session: AsyncSession, username: str) -> User:
    user = User(
        name="Gate Test",
        username=username,
        email=f"{username}@example.com",
        hashed_password="not-a-real-hash",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_plugin(session: AsyncSession, name: str, enabled: bool) -> Plugin:
    plugin = Plugin(name=name, enabled=enabled)
    session.add(plugin)
    await session.commit()
    await session.refresh(plugin)
    return plugin


async def _raise_operational_error(username: str, session: AsyncSession) -> User | None:
    """Stand in for the user lookup when the database is unreachable."""
    raise OperationalError("SELECT 1", {}, Exception("connection lost"))


async def _seed_user_plugin(session: AsyncSession, user: User, plugin: Plugin, enabled: bool) -> None:
    session.add(UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), enabled=enabled))
    await session.commit()


class TestRoutePluginResolution:
    """Which plugin owns the requested URL."""

    @pytest.mark.parametrize(
        "method, path, plugin_name",
        [
            ("POST", CHAT_COMPLETIONS_PATH, "chat"),
            ("GET", "/api/v1/slack/oauth/status", "slack"),
            ("GET", "/api/v1/google-drive/oauth/status", "google-drive"),
        ],
    )
    def test_resolves_the_plugin_that_owns_a_plugin_route(self, method: str, path: str, plugin_name: str) -> None:
        # Every plugin that mounts routes, not just one: these routers nest their includes to
        # different depths, and a plugin the gate cannot name is a plugin it cannot police.
        app = assemble_app()
        middleware = PluginAccessMiddleware(app)

        assert middleware._get_route_plugin_name(_request(app, method, path)) == plugin_name

    def test_returns_none_for_a_core_route(self) -> None:
        app = assemble_app()
        middleware = PluginAccessMiddleware(app)

        assert middleware._get_route_plugin_name(_request(app, "GET", "/api/v1/user/me")) is None

    def test_returns_none_for_an_unknown_path(self) -> None:
        app = assemble_app()
        middleware = PluginAccessMiddleware(app)

        assert middleware._get_route_plugin_name(_request(app, "GET", "/api/v1/nothing-here")) is None


class TestExcludedPaths:
    """Which paths the gate declines to police."""

    def test_does_not_exclude_plugin_paths_by_default(self) -> None:
        # exclude_paths is matched with startswith, so a "/" entry would exclude every path
        # there is and leave the gate enforcing nothing at all.
        middleware = PluginAccessMiddleware(assemble_app())

        assert middleware._is_excluded_path(CHAT_COMPLETIONS_PATH) is False

    def test_excludes_the_configured_paths(self) -> None:
        middleware = PluginAccessMiddleware(assemble_app(), ["/api/v1/auth"])

        assert middleware._is_excluded_path("/api/v1/auth/login") is True


class TestPluginAccessGate:
    """What the gate does with a real request."""

    async def test_blocks_a_plugin_the_user_disabled(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _seed_user(session, "disabled-chat-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, user, plugin, False)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code == 403
        assert "chat" in response.json()["detail"]

    async def test_blocks_a_plugin_disabled_system_wide(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _seed_user(session, "system-disabled-user")
        plugin = await _seed_plugin(session, "chat", False)
        await _seed_user_plugin(session, user, plugin, True)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code == 403
        assert "chat" in response.json()["detail"]

    async def test_lets_through_a_plugin_the_user_enabled(self, client: AsyncClient, session: AsyncSession) -> None:
        # The inverse of the block: without it, a gate that rejects everything would pass the
        # tests above while breaking every plugin endpoint in the product.
        user = await _seed_user(session, "enabled-chat-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, user, plugin, True)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code != 403

    async def test_lets_through_a_plugin_with_no_user_preference(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        user = await _seed_user(session, "no-preference-user")
        await _seed_plugin(session, "chat", True)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code != 403

    async def test_does_not_gate_core_routes(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _seed_user(session, "core-route-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, user, plugin, False)

        response = await client.get("/api/v1/user/me", headers=_auth_headers(user.username))

        assert response.status_code == 200

    async def test_does_not_gate_anonymous_requests(self, client: AsyncClient, session: AsyncSession) -> None:
        # Unauthenticated plugin endpoints exist — Slack's OAuth callback is called by Slack
        # itself, with no bearer token. Per-user access is meaningless without a user, so the
        # gate must fail open rather than block the callback.
        user = await _seed_user(session, "slack-callback-user")
        plugin = await _seed_plugin(session, "slack", True)
        await _seed_user_plugin(session, user, plugin, False)

        response = await client.get(SLACK_CALLBACK_PATH)

        assert response.status_code == 422

    async def test_lets_through_a_token_naming_a_user_that_does_not_exist(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        # Nobody to hold a preference, so there is nothing to enforce. The route's own auth
        # dependency is what rejects the request.
        await _seed_plugin(session, "chat", True)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers("no-such-user"),
        )

        assert response.status_code != 403
        assert response.json()["detail"] == "User not found"

    async def test_blocks_when_the_access_lookup_fails(
        self, client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The gate fails closed: a lookup it could not complete is not permission to proceed.
        user = await _seed_user(session, "db-error-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, user, plugin, True)
        monkeypatch.setattr("sparkth.core.plugins.middleware.get_user_by_username", _raise_operational_error)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code == 403
        assert "chat" in response.json()["detail"]

    async def test_lets_through_a_request_carrying_an_invalid_token(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        # An unreadable token identifies nobody, so there is no per-user preference to enforce.
        # The route's own auth dependency still rejects the request.
        plugin = await _seed_plugin(session, "chat", True)
        user = await _seed_user(session, "invalid-token-user")
        await _seed_user_plugin(session, user, plugin, False)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.json()["detail"] == "Could not validate credentials"
