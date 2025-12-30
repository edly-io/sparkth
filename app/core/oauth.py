"""
OAuth 2.0 utility functions for token generation and validation.
"""

import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_client_id() -> str:
    """Generate a unique client ID."""
    return f"client_{secrets.token_urlsafe(32)}"


def generate_client_secret() -> str:
    """Generate a secure client secret."""
    return secrets.token_urlsafe(48)


def hash_client_secret(secret: str) -> str:
    """Hash a client secret for storage."""
    return pwd_context.hash(secret)


def verify_client_secret(plain_secret: str, hashed_secret: str) -> bool:
    """Verify a client secret against its hash."""
    return pwd_context.verify(plain_secret, hashed_secret)


def generate_authorization_code() -> str:
    """Generate a secure authorization code."""
    return secrets.token_urlsafe(32)


def generate_access_token() -> str:
    """Generate a secure access token."""
    return secrets.token_urlsafe(48)


def generate_refresh_token() -> str:
    """Generate a secure refresh token."""
    return secrets.token_urlsafe(48)


def get_authorization_code_expiry() -> datetime:
    """Get the expiration datetime for an authorization code."""
    return datetime.now(timezone.utc) + timedelta(minutes=settings.OAUTH_AUTHORIZATION_CODE_EXPIRE_MINUTES)


def get_access_token_expiry() -> datetime:
    """Get the expiration datetime for an access token."""
    return datetime.now(timezone.utc) + timedelta(days=settings.OAUTH_ACCESS_TOKEN_EXPIRE_DAYS)


def get_refresh_token_expiry() -> datetime:
    """Get the expiration datetime for a refresh token."""
    return datetime.now(timezone.utc) + timedelta(days=settings.OAUTH_REFRESH_TOKEN_EXPIRE_DAYS)


def parse_scope(scope_string: str) -> set[str]:
    """Parse a space-separated scope string into a set of scopes."""
    if not scope_string:
        return set()
    return set(scope_string.split())


def format_scope(scopes: set[str]) -> str:
    """Format a set of scopes into a space-separated string."""
    return " ".join(sorted(scopes))
