"""Request-context plumbing: the middleware seeds per-request origin metadata
into a contextvar so deep call sites (tool executors, services) can attribute
events without threading a request object through every layer."""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

import pytest

from app.core.audit.middleware import AuditContextMiddleware
from app.lib.audit.context import (
    AnonymousActor,
    AuditActorType,
    AuditRequestContext,
    AuditSource,
    AuditSystemContext,
    SystemActor,
    UserActor,
    audit_context,
    bind_audit_actor,
    current_audit_context,
)
from app.lib.settings import get_settings

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


def _http_scope(headers: list[tuple[bytes, bytes]]) -> Scope:
    return {"type": "http", "method": "GET", "path": "/", "headers": headers, "client": ("1.2.3.4", 1234)}


async def _receive() -> Message:
    return {"type": "http.request"}


async def _send(message: Message) -> None:
    return None


async def test_default_context_is_empty() -> None:
    context = current_audit_context()
    assert context.request_id is None
    assert context.actor is None


async def test_middleware_seeds_request_metadata() -> None:
    seen: dict[str, AuditRequestContext | AuditSystemContext] = {}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen["context"] = current_audit_context()

    middleware = AuditContextMiddleware(app)
    await middleware(_http_scope(headers=[(b"user-agent", b"pytest-agent")]), _receive, _send)

    context = seen["context"]
    assert context.request_id is not None
    assert context.request_ip == "1.2.3.4"
    assert context.user_agent == "pytest-agent"
    assert context.source == AuditSource.REST


async def _ip_seen_by_app(headers: list[tuple[bytes, bytes]]) -> str | None:
    seen: dict[str, AuditRequestContext | AuditSystemContext] = {}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen["context"] = current_audit_context()

    middleware = AuditContextMiddleware(app)
    await middleware(_http_scope(headers=headers), _receive, _send)
    return seen["context"].request_ip


async def test_xff_is_ignored_without_trusted_proxies() -> None:
    # Default TRUSTED_PROXY_HOPS=0: the client-controlled header must not
    # become audit evidence; the socket peer is used instead.
    ip = await _ip_seen_by_app([(b"x-forwarded-for", b"6.6.6.6")])
    assert ip == "1.2.3.4"


async def test_xff_takes_nth_from_right_per_trusted_hops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 1)
    ip = await _ip_seen_by_app([(b"x-forwarded-for", b"6.6.6.6, 9.9.9.9, 10.0.0.1")])
    assert ip == "10.0.0.1"

    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 2)
    ip = await _ip_seen_by_app([(b"x-forwarded-for", b"6.6.6.6, 9.9.9.9, 10.0.0.1")])
    assert ip == "9.9.9.9"


async def test_xff_chain_shorter_than_trusted_hops_falls_back_to_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 3)
    ip = await _ip_seen_by_app([(b"x-forwarded-for", b"9.9.9.9, 10.0.0.1")])
    assert ip == "1.2.3.4"


async def test_middleware_resets_context_after_request() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        return None

    middleware = AuditContextMiddleware(app)
    await middleware(_http_scope(headers=[]), _receive, _send)

    assert current_audit_context().request_id is None


async def test_middleware_passes_non_http_scopes_through_untouched() -> None:
    called: dict[str, bool] = {}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        called["yes"] = True
        assert current_audit_context().request_id is None

    middleware = AuditContextMiddleware(app)
    await middleware({"type": "lifespan"}, _receive, _send)
    assert called["yes"]


async def test_bind_audit_actor_sets_actor_on_current_context() -> None:
    with audit_context(AuditSystemContext()):
        bind_audit_actor(UserActor(id="7", label="alice"))
        actor = current_audit_context().actor
        assert actor is not None
        assert actor.id == "7"
        assert actor.label == "alice"


def test_system_context_never_carries_request_metadata() -> None:
    context = AuditSystemContext(source=AuditSource.CLI)
    assert context.request_id is None
    assert context.request_ip is None
    assert context.user_agent is None


def test_request_context_requires_a_request_id() -> None:
    with pytest.raises(TypeError):
        AuditRequestContext()  # type: ignore[call-arg]


def test_actor_type_is_fixed_per_class() -> None:
    assert UserActor(id="1").type is AuditActorType.USER
    assert SystemActor().type is AuditActorType.SYSTEM
    assert AnonymousActor().type is AuditActorType.ANONYMOUS


def test_user_actor_requires_an_id() -> None:
    with pytest.raises(TypeError):
        UserActor()  # type: ignore[call-arg]


def test_system_and_anonymous_actors_never_carry_an_id() -> None:
    assert SystemActor(label="cli").id is None
    assert AnonymousActor(label="mallory").id is None
