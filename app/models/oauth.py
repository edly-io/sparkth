"""
OAuth 2.0 models for client applications, authorization codes, and access tokens.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import JSON, Column, Field

from app.models.base import TimestampedModel


class OAuthClient(TimestampedModel, table=True):
    """OAuth client application registration."""

    __tablename__ = "oauth_clients"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: str = Field(max_length=255, unique=True, index=True)
    client_secret_hash: str = Field(max_length=255)  # Hashed client secret
    client_name: str = Field(max_length=255)
    redirect_uris: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    user_id: int = Field(foreign_key="user.id", index=True)
    is_active: bool = Field(default=True)


class OAuthAuthorizationCode(TimestampedModel, table=True):
    """Temporary authorization code for OAuth flow."""

    __tablename__ = "oauth_authorization_codes"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=255, unique=True, index=True)
    client_id: str = Field(max_length=255, foreign_key="oauth_clients.client_id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    redirect_uri: str = Field(max_length=512)
    scope: str = Field(default="", max_length=255)  # Space-separated scopes
    expires_at: datetime = Field(index=True)
    is_used: bool = Field(default=False)  # Prevent code reuse

    def is_expired(self) -> bool:
        """Check if the authorization code has expired."""
        # Make expires_at timezone-aware if it's naive
        expires_at = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        return datetime.now(timezone.utc) > expires_at


class OAuthAccessToken(TimestampedModel, table=True):
    """OAuth access token for API authentication."""

    __tablename__ = "oauth_access_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    access_token: str = Field(max_length=255, unique=True, index=True)
    refresh_token: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)
    client_id: str = Field(max_length=255, foreign_key="oauth_clients.client_id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    scope: str = Field(default="", max_length=255)  # Space-separated scopes
    expires_at: datetime = Field(index=True)
    refresh_token_expires_at: Optional[datetime] = Field(default=None, index=True)
    is_revoked: bool = Field(default=False, index=True)

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        # Make expires_at timezone-aware if it's naive
        expires_at = self.expires_at.replace(tzinfo=timezone.utc) if self.expires_at.tzinfo is None else self.expires_at
        return datetime.now(timezone.utc) > expires_at

    def is_refresh_token_expired(self) -> bool:
        """Check if the refresh token has expired."""
        if not self.refresh_token_expires_at:
            return True
        # Make refresh_token_expires_at timezone-aware if it's naive
        refresh_expires_at = self.refresh_token_expires_at.replace(tzinfo=timezone.utc) if self.refresh_token_expires_at.tzinfo is None else self.refresh_token_expires_at
        return datetime.now(timezone.utc) > refresh_expires_at
