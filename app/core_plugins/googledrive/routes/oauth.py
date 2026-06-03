"""Google Drive OAuth endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session, get_session
from app.core_plugins.googledrive.oauth import (
    decode_state,
    decrypt_token,
    delete_token,
    exchange_code_for_tokens,
    generate_authorization_url,
    get_token_record,
    get_user_info,
    revoke_token,
    save_tokens,
)
from app.core_plugins.googledrive.routes.dependencies import get_valid_access_token, require_user_id
from app.core_plugins.googledrive.routes.route_utils import get_drive_credentials
from app.core_plugins.googledrive.types import AuthorizationUrlResponse, ConnectionStatusResponse
from app.lib.log import get_logger
from app.models.user import User

router = APIRouter()
logger = get_logger(__name__)


@router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(
    current_user: User = Depends(get_current_user),
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> AuthorizationUrlResponse:
    """Generate Google OAuth authorization URL."""
    client_id, _, redirect_uri = get_drive_credentials()
    url = generate_authorization_url(user_id, client_id, redirect_uri, login_hint=current_user.email)
    return AuthorizationUrlResponse(url=url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    """Handle OAuth callback from Google."""
    from itsdangerous import BadSignature, SignatureExpired

    try:
        state_data = decode_state(state)
        user_id = state_data["user_id"]
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired. Please try again.")
    except (BadSignature, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    client_id, client_secret, redirect_uri = get_drive_credentials()

    try:
        token_data = await exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange authorization code.")

    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        existing = await get_token_record(session, user_id)
        if existing:
            refresh_token = decrypt_token(existing.refresh_token_encrypted)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token received. Please disconnect and reconnect Google Drive.",
        )

    try:
        await save_tokens(
            session,
            user_id,
            token_data["access_token"],
            refresh_token,
            token_data["expires_in"],
            token_data.get("scope", ""),
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save tokens.",
        )

    return RedirectResponse(url="/dashboard/resources?connected=true")


@router.delete("/oauth/disconnect")
async def disconnect_drive(
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Disconnect Google Drive by revoking and deleting tokens."""
    token_record = await get_token_record(session, user_id)
    if not token_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Google Drive not connected")

    try:
        access_token = decrypt_token(token_record.access_token_encrypted)
        await revoke_token(access_token)
    except ValueError:
        logger.warning("Failed to decrypt token for revocation, proceeding with deletion")

    await delete_token(session, user_id)
    return {"detail": "Google Drive disconnected successfully"}


@router.get("/oauth/status", response_model=ConnectionStatusResponse)
async def get_connection_status(
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> ConnectionStatusResponse:
    """Get Google Drive connection status."""
    token_record = await get_token_record(session, user_id)
    if not token_record:
        return ConnectionStatusResponse(connected=False)

    try:
        client_id, client_secret, _ = get_drive_credentials()
        access_token = await get_valid_access_token(session, user_id, client_id, client_secret)
        user_info = await get_user_info(access_token)
        return ConnectionStatusResponse(
            connected=True,
            email=user_info.get("email"),
            expires_at=token_record.token_expiry,
        )
    except (ValueError, HTTPException):
        return ConnectionStatusResponse(connected=False)
