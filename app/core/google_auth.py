"""Google OAuth 2.0 authentication for user login."""

from typing import Any
from urllib.parse import urlencode

import aiohttp

from app.core.config import get_settings

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for login (openid, email, profile)
GOOGLE_LOGIN_SCOPES = [
    "openid",
    "email",
    "profile",
]


def get_google_credentials() -> tuple[str, str, str]:
    """Get Google OAuth credentials from settings."""
    settings = get_settings()

    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")

    return settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, settings.GOOGLE_AUTH_REDIRECT_URI


def generate_google_login_url() -> str:
    """
    Generate Google OAuth authorization URL for login.

    Returns:
        The authorization URL to redirect the user to.
    """
    client_id, _, redirect_uri = get_google_credentials()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_LOGIN_SCOPES),
        "access_type": "offline",
        "prompt": "select_account",
    }

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_auth_code(code: str) -> dict[str, Any]:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: The authorization code from Google OAuth callback.

    Returns:
        Dictionary containing access_token, refresh_token, expires_in, etc.

    Raises:
        ValueError: If token exchange fails.
    """
    client_id, client_secret, redirect_uri = get_google_credentials()

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GOOGLE_TOKEN_URL, data=data) as response:
            if response.status != 200:
                error_data = await response.json()
                raise ValueError(f"Token exchange failed: {error_data}")
            result: dict[str, Any] = await response.json()
            return result


async def get_google_user_info(access_token: str) -> dict[str, Any]:
    """
    Get Google user info using access token.

    Args:
        access_token: Valid Google access token.

    Returns:
        Dictionary containing user info (id, email, name, picture, etc.).

    Raises:
        ValueError: If fetching user info fails.
    """
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.get(GOOGLE_USERINFO_URL, headers=headers) as response:
            if response.status != 200:
                raise ValueError("Failed to get user info from Google")
            result: dict[str, Any] = await response.json()
            return result
