"""Behavioural tests for the per-user plugin access gate (PluginAccessMiddleware).

The gate answers one question before a request reaches its route: does the caller still
have this plugin turned on? Each test drives a real request through the assembled app so
the whole chain is exercised — resolving which plugin owns the URL, resolving the caller
from the bearer token, and the access lookup itself.
"""

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, cast

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import RouteContext, iter_route_contexts
from httpx import AsyncClient
from sqlalchemy import event, inspect
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.routing import BaseRoute

from sparkth.core.db import get_engine
from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.core.plugins.middleware import PluginAccessMiddleware
from sparkth.core.security import create_access_token
from sparkth.main import assemble_app

CHAT_COMPLETIONS_PATH = "/api/v1/chat/completions"
SLACK_CALLBACK_PATH = "/api/v1/slack/oauth/callback"


class _CountingFlattener:
    """Stands in for ``iter_route_contexts``, recording how often the table is flattened."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, routes: Sequence[BaseRoute]) -> Iterator[RouteContext]:
        self.calls += 1
        return iter_route_contexts(routes)


# The user table, quoted or not, but never the user_plugins table beside it.
_USER_SELECT = re.compile(r'^select\b.*\bfrom\s+"?user"?(\s|$)')


class _UserSelectCounter:
    """Counts the SELECTs issued against the user table on the shared engine."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if _USER_SELECT.match(" ".join(statement.split()).lower()):
            self.count += 1


@contextmanager
def _counting_user_selects() -> Iterator[_UserSelectCounter]:
    """Count user-table reads for the duration of the block."""
    counter = _UserSelectCounter()
    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", counter)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", counter)


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

    def test_flattens_the_route_table_once_and_reuses_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The table is fixed once the app is assembled, so flattening it per request is
        repeated work on a path every request takes. Resolution must stay correct across
        both requests — a cache that answers the second one wrongly is worse than no cache."""
        app = assemble_app()
        middleware = PluginAccessMiddleware(app)
        flattener = _CountingFlattener()
        monkeypatch.setattr("sparkth.core.plugins.middleware.iter_route_contexts", flattener)

        first = middleware._get_route_plugin_name(_request(app, "POST", CHAT_COMPLETIONS_PATH))
        second = middleware._get_route_plugin_name(_request(app, "GET", "/api/v1/slack/oauth/status"))

        assert (first, second) == ("chat", "slack")
        assert flattener.calls == 1


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

    async def test_blocks_a_plugin_disabled_system_wide_for_a_user_with_no_preference(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """The system switch does not depend on the caller having a preference row, and most
        callers have none. Resolving the switch and the preference together must keep the
        plugin's own row even when nothing joins to it — otherwise the administrative
        control silently stops applying to exactly the users who never opened their
        settings."""
        user = await _seed_user(session, "no-preference-system-disabled")
        await _seed_plugin(session, "chat", False)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code == 403
        assert "chat" in response.json()["detail"]

    async def test_lets_through_a_plugin_only_another_user_disabled(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """The preference read must be the caller's own. Resolving the plugin and the
        preference together means keying that lookup on the user as well — miss it, and one
        user turning a plugin off would turn it off for everybody."""
        caller = await _seed_user(session, "unaffected-caller")
        other = await _seed_user(session, "opted-out-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, other, plugin, False)

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(caller.username),
        )

        assert response.status_code != 403

    async def test_lets_through_a_plugin_the_registry_has_never_seen(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """No row is not the same as a disabled row: a plugin absent from the registry
        stays reachable rather than being treated as switched off."""
        user = await _seed_user(session, "unregistered-plugin-user")

        response = await client.post(
            CHAT_COMPLETIONS_PATH,
            json={"messages": []},
            headers=_auth_headers(user.username),
        )

        assert response.status_code != 403

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


class TestCallerIsResolvedOnce:
    """The gate and ``get_current_user`` answer the same question about the same request,
    so the second one reuses the first one's answer instead of repeating the work."""

    async def test_a_gated_route_reads_the_user_once(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _seed_user(session, "reuse-user")
        plugin = await _seed_plugin(session, "chat", True)
        await _seed_user_plugin(session, user, plugin, True)

        with _counting_user_selects() as counter:
            await client.post(
                CHAT_COMPLETIONS_PATH,
                json={"messages": []},
                headers=_auth_headers(user.username),
            )

        assert counter.count == 1

    async def test_an_ungated_route_still_reads_the_user(self, client: AsyncClient, session: AsyncSession) -> None:
        """A core route never reaches the gate, so nothing has been loaded for the
        dependency to reuse and it must still resolve the caller itself."""
        user = await _seed_user(session, "core-route-user")

        with _counting_user_selects() as counter:
            response = await client.get("/api/v1/user/me", headers=_auth_headers(user.username))

        assert response.status_code == 200
        assert counter.count == 1

    def test_the_user_model_carries_no_relationships(self) -> None:
        """What makes handing the loaded user to the route safe: the gate's session has
        closed by then, so the instance the route receives is detached. Detached is
        harmless for plain columns and raises on a relationship — adding one to ``User``
        would make this reuse unsafe, so the guard fails loudly rather than at runtime."""
        assert list(inspect(User).relationships) == []
