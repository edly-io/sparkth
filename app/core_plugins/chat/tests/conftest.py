from app.core_plugins.chat.routes import chat_router
from app.main import app

_CHAT_PREFIX = "/api/v1"
_chat_routes_registered = False


def _ensure_chat_routes() -> None:
    global _chat_routes_registered
    if _chat_routes_registered:
        return
    existing = {getattr(r, "path", None) for r in app.routes}
    if f"{_CHAT_PREFIX}/chat/completions" not in existing:
        app.include_router(chat_router, prefix=_CHAT_PREFIX)
    _chat_routes_registered = True


_ensure_chat_routes()
