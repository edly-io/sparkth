"""ASGI middleware that seeds the per-request audit context."""

from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.audit.context import AuditRequestContext, audit_context
from app.core.audit.enums import AuditSource
from app.lib.settings import get_settings


class AuditContextMiddleware:
    """Seed request id, client IP, and user agent into the audit contextvar.

    Pure ASGI (no BaseHTTPMiddleware) so it adds no response buffering. The
    actor is bound later by the authentication dependency; this middleware only
    captures what is known at the edge.

    The recorded IP is audit evidence, so ``X-Forwarded-For`` (which any
    client can forge) is only honored when ``TRUSTED_PROXY_HOPS`` says how
    many proxies in front of the app are trusted; with the default of 0 the
    socket peer address is used.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        context = AuditRequestContext(
            request_id=uuid4().hex,
            request_ip=self._client_ip(scope, headers),
            user_agent=headers.get("user-agent"),
            source=AuditSource.REST,
        )
        with audit_context(context):
            await self.app(scope, receive, send)

    @staticmethod
    def _client_ip(scope: Scope, headers: dict[str, str]) -> str | None:
        """Resolve the client IP without trusting client-forgeable input.

        Each proxy appends the address it received the connection from to
        ``X-Forwarded-For``, so only the last ``TRUSTED_PROXY_HOPS`` entries
        were written by proxies we control; the Nth-from-right entry is the
        address the outermost trusted proxy saw. Everything left of it, and
        the whole header when no proxies are trusted, is client-supplied and
        ignored in favor of the socket peer.
        """
        client = scope.get("client")
        peer: str | None = client[0] if client else None
        trusted_hops = get_settings().TRUSTED_PROXY_HOPS
        forwarded = headers.get("x-forwarded-for")
        if trusted_hops and forwarded:
            chain = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
            if len(chain) >= trusted_hops:
                return chain[-trusted_hops]
        return peer
