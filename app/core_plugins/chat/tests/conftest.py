from app.core_plugins.chat.routes import chat_router
from app.main import app  # must be imported before chat_router to avoid circular imports
from tests.lib.routes import register_router

register_router(app, chat_router, sentinel_path="/api/v1/chat/completions", prefix="/api/v1")
