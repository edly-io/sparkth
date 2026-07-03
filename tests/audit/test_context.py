"""Request-context plumbing: the middleware seeds per-request origin metadata
into a contextvar so deep call sites (tool executors, services) can attribute
events without threading a request object through every layer."""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from app.core.audit.middleware import AuditContextMiddleware
from app.lib.audit import AuditActor, AuditContext, AuditSource, audit_context, bind_audit_actor, current_audit_context

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
    seen: dict[str, AuditContext] = {}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen["context"] = current_audit_context()

    middleware = AuditContextMiddleware(app)
    await middleware(_http_scope(headers=[(b"user-agent", b"pytest-agent")]), _receive, _send)

    context = seen["context"]
    assert context.request_id is not None
    assert context.request_ip == "1.2.3.4"
    assert context.user_agent == "pytest-agent"
    assert context.source == AuditSource.REST


async def test_middleware_prefers_x_forwarded_for_first_hop() -> None:
    seen: dict[str, AuditContext] = {}

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen["context"] = current_audit_context()

    middleware = AuditContextMiddleware(app)
    headers = [(b"x-forwarded-for", b"9.9.9.9, 10.0.0.1")]
    await middleware(_http_scope(headers=headers), _receive, _send)

    assert seen["context"].request_ip == "9.9.9.9"


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
    with audit_context(AuditContext()):
        bind_audit_actor(AuditActor(type="user", id="7", label="alice"))
        actor = current_audit_context().actor
        assert actor is not None
        assert actor.id == "7"
        assert actor.label == "alice"
