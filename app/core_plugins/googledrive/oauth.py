"""OAuth 2.0 flow handlers for Google Drive authentication."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp
from itsdangerous import URLSafeSerializer
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.drive import DriveOAuthToken

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

# Required scopes for Google Drive access
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_serializer() -> URLSafeSerializer:
    """Get serializer for encrypting/decrypting OAuth tokens."""
    settings = get_settings()
    return URLSafeSerializer(settings.SECRET_KEY, salt="google-drive-oauth")


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token for storage."""
    serializer = get_serializer()
    return serializer.dumps(token)


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an OAuth token from storage."""
    serializer = get_serializer()
    token: str = serializer.loads(encrypted_token)
    return token


def generate_authorization_url(user_id: int, client_id: str, redirect_uri: str, login_hint: str | None = None) -> str:
    """Generate Google OAuth authorization URL.

    Args:
        user_id: The user ID to include in the state parameter.
        client_id: Google OAuth client ID.
        redirect_uri: OAuth callback redirect URI.
        login_hint: Email address to pre-select the Google account.

    Returns:
        The authorization URL to redirect the user to.
    """
    from urllib.parse import urlencode

    serializer = get_serializer()
    state = serializer.dumps({"user_id": user_id})

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "state": state,
    }

    if login_hint:
        params["login_hint"] = login_hint

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def decode_state(state: str) -> dict[str, Any]:
    """Decode the state parameter from OAuth callback."""
    serializer = get_serializer()
    result: dict[str, Any] = serializer.loads(state)
    return result


async def exchange_code_for_tokens(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(GOOGLE_TOKEN_URL, data=data) as response:
            if response.status != 200:
                error_data = await response.json()
                raise ValueError(f"Token exchange failed: {error_data}")
            result: dict[str, Any] = await response.json()
            return result


async def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict[str, Any]:
    """Refresh an expired access token."""
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(GOOGLE_TOKEN_URL, data=data) as response:
            if response.status != 200:
                error_data = await response.json()
                raise ValueError(f"Token refresh failed: {error_data}")
            result: dict[str, Any] = await response.json()
            return result


async def get_user_info(access_token: str) -> dict[str, Any]:
    """Get Google user info using access token."""
    async with aiohttp.ClientSession() as http_session:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with http_session.get(GOOGLE_USERINFO_URL, headers=headers) as response:
            if response.status != 200:
                raise ValueError("Failed to get user info")
            result: dict[str, Any] = await response.json()
            return result


async def revoke_token(token: str) -> bool:
    """Revoke a Google OAuth token."""
    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(GOOGLE_REVOKE_URL, data={"token": token}) as response:
            return response.status == 200


def save_tokens(
    session: Session,
    user_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    scopes: str,
) -> DriveOAuthToken:
    """Save OAuth tokens to database."""
    token_expiry = _utc_now() + timedelta(seconds=expires_in)

    statement = select(DriveOAuthToken).where(DriveOAuthToken.user_id == user_id)
    existing = session.exec(statement).first()

    if existing:
        if existing.is_deleted:
            existing.restore()
        existing.access_token_encrypted = encrypt_token(access_token)
        existing.refresh_token_encrypted = encrypt_token(refresh_token)
        existing.token_expiry = token_expiry
        existing.scopes = scopes
        existing.update_timestamp()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    token_record = DriveOAuthToken(
        user_id=user_id,
        access_token_encrypted=encrypt_token(access_token),
        refresh_token_encrypted=encrypt_token(refresh_token),
        token_expiry=token_expiry,
        scopes=scopes,
    )
    session.add(token_record)
    session.commit()
    session.refresh(token_record)
    return token_record


def get_token_record(session: Session, user_id: int) -> Optional[DriveOAuthToken]:
    """Get OAuth token record for a user."""
    statement = select(DriveOAuthToken).where(DriveOAuthToken.user_id == user_id, DriveOAuthToken.is_deleted == False)
    return session.exec(statement).first()


async def get_valid_access_token(session: Session, user_id: int, client_id: str, client_secret: str) -> str:
    """Get a valid access token for a user, refreshing if necessary."""
    token_record = get_token_record(session, user_id)
    if not token_record:
        raise ValueError("Google Drive not connected")

    now = _utc_now()
    buffer = timedelta(minutes=5)

    token_expiry = token_record.token_expiry
    if token_expiry.tzinfo is None:
        token_expiry = token_expiry.replace(tzinfo=timezone.utc)

    if token_expiry <= now + buffer:
        refresh_tok = decrypt_token(token_record.refresh_token_encrypted)
        token_data = await refresh_access_token(refresh_tok, client_id, client_secret)

        save_tokens(
            session,
            user_id,
            token_data["access_token"],
            refresh_tok,
            token_data["expires_in"],
            token_record.scopes,
        )

        access_token: str = token_data["access_token"]
        return access_token

    return decrypt_token(token_record.access_token_encrypted)


def delete_token(session: Session, user_id: int) -> bool:
    """Delete OAuth token record for a user (soft delete)."""
    token_record = get_token_record(session, user_id)
    if not token_record:
        return False

    token_record.soft_delete()
    session.add(token_record)
    session.commit()
    return True
