import app.rag.db_models  # noqa: F401 — loads RAG tables into SQLModel metadata for Alembic autogenerate

from .drive import DriveFile, DriveFolder, DriveOAuthToken
from .email_verification import EmailVerificationToken
from .llm import LLMConfig
from .plugin import Plugin, UserPlugin
from .user import User
from .whitelist import WhitelistedEmail

__all__ = [
    "User",
    "Plugin",
    "UserPlugin",
    "DriveOAuthToken",
    "DriveFolder",
    "DriveFile",
    "LLMConfig",
    "WhitelistedEmail",
    "EmailVerificationToken",
]
