"""ASGI middleware that seeds the per-request audit context."""

from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.audit.context import AuditContext, audit_context
from app.core.audit.enums import AuditSource


class AuditContextMiddleware:
    """Seed request id, client IP, and user agent into the audit contextvar.

    Pure ASGI (no BaseHTTPMiddleware) so it adds no response buffering. The
    actor is bound later by the authentication dependency; this middleware only
    captures what is known at the edge.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        context = AuditContext(
            request_id=uuid4().hex,
            request_ip=self._client_ip(scope, headers),
            user_agent=headers.get("user-agent"),
            source=AuditSource.REST,
        )
        with audit_context(context):
            await self.app(scope, receive, send)

    @staticmethod
    def _client_ip(scope: Scope, headers: dict[str, str]) -> str | None:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else None
