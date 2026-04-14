"""FastAPI routes for the Slack TA Bot plugin."""

from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core_plugins.slack.oauth import (
    decode_state,
    delete_workspace,
    exchange_code_for_tokens,
    generate_authorization_url,
    get_workspace,
    save_workspace,
)
from app.core_plugins.slack.types import AuthorizationUrlResponse, ConnectionStatusResponse
from app.models.user import User

router: APIRouter = APIRouter()
logger = getLogger(__name__)


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id


def get_slack_credentials() -> tuple[str, str, str, str]:
    """Return (client_id, client_secret, redirect_uri, signing_secret).

    Raises HTTPException 400 if any credential is missing.
    """
    s = get_settings()
    if not s.SLACK_CLIENT_ID or not s.SLACK_CLIENT_SECRET or not s.SLACK_SIGNING_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack credentials not configured. Set SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_SIGNING_SECRET.",
        )
    return s.SLACK_CLIENT_ID, s.SLACK_CLIENT_SECRET, s.SLACK_REDIRECT_URI, s.SLACK_SIGNING_SECRET


@router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(user_id: int = Depends(require_user_id)) -> AuthorizationUrlResponse:
    """Return the Slack OAuth install URL."""
    client_id, _, redirect_uri, _ = get_slack_credentials()
    url = generate_authorization_url(user_id, client_id, redirect_uri)
    return AuthorizationUrlResponse(url=url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle Slack OAuth redirect, persist workspace token."""
    from itsdangerous import BadSignature, SignatureExpired

    try:
        state_data = decode_state(state)
        user_id = state_data["user_id"]
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired. Please try again.")
    except (BadSignature, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    client_id, client_secret, redirect_uri, _ = get_slack_credentials()

    try:
        token_data = await exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
    except ValueError as exc:
        logger.error("Slack OAuth code exchange failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Slack authorization code."
        )

    try:
        save_workspace(
            session,
            user_id=user_id,
            team_id=token_data["team"]["id"],
            team_name=token_data["team"]["name"],
            bot_token=token_data["access_token"],
            bot_user_id=token_data["bot_user_id"],
        )
    except (KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected response from Slack. Please try again.",
        )

    return RedirectResponse(url="/dashboard/slack?connected=true")


@router.delete("/oauth/disconnect")
def disconnect_workspace(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Disconnect the Slack workspace for the current user."""
    if not get_workspace(session, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack workspace not connected")
    delete_workspace(session, user_id)
    return {"detail": "Slack workspace disconnected successfully"}


@router.get("/oauth/status", response_model=ConnectionStatusResponse)
def get_connection_status(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> ConnectionStatusResponse:
    """Return Slack connection status for the current user."""
    workspace = get_workspace(session, user_id)
    if not workspace:
        return ConnectionStatusResponse(connected=False)
    return ConnectionStatusResponse(
        connected=True,
        team_name=workspace.team_name,
        team_id=workspace.team_id,
        bot_user_id=workspace.bot_user_id,
        connected_at=workspace.created_at,
    )
