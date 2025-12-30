"""
OAuth 2.0 Pydantic schemas for request/response models.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class OAuthClientCreate(BaseModel):
    """Request model for creating an OAuth client."""

    client_name: str = Field(..., min_length=1, max_length=255, description="Name of the OAuth client application")
    redirect_uris: list[str] = Field(..., min_items=1, description="List of valid redirect URIs")


class OAuthClientResponse(BaseModel):
    """Response model for OAuth client (includes secret only on creation)."""

    id: int
    client_id: str
    client_name: str
    redirect_uris: list[str]
    user_id: int
    is_active: bool
    created_at: datetime
    client_secret: str | None = Field(default=None, description="Only returned on creation")


class OAuthAuthorizeRequest(BaseModel):
    """Request model for OAuth authorization endpoint."""

    response_type: str = Field(default="code", description="Must be 'code' for authorization code flow")
    client_id: str
    redirect_uri: str
    scope: str = Field(default="", description="Space-separated list of scopes")
    state: str | None = Field(default=None, description="Optional state parameter for CSRF protection")


class OAuthTokenRequest(BaseModel):
    """Request model for OAuth token endpoint."""

    grant_type: str = Field(..., description="Either 'authorization_code' or 'refresh_token'")
    code: str | None = Field(default=None, description="Authorization code (required for authorization_code grant)")
    redirect_uri: str | None = Field(default=None, description="Redirect URI (required for authorization_code grant)")
    refresh_token: str | None = Field(default=None, description="Refresh token (required for refresh_token grant)")
    client_id: str
    client_secret: str


class OAuthTokenResponse(BaseModel):
    """Response model for OAuth token endpoint."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")
    refresh_token: str | None = None
    scope: str = ""


class OAuthRevokeRequest(BaseModel):
    """Request model for OAuth token revocation."""

    token: str = Field(..., description="The token to revoke")
    token_type_hint: str | None = Field(default=None, description="Either 'access_token' or 'refresh_token'")
    client_id: str
    client_secret: str


class OAuthClientListResponse(BaseModel):
    """Response model for listing OAuth clients."""

    id: int
    client_id: str
    client_name: str
    redirect_uris: list[str]
    is_active: bool
    created_at: datetime
