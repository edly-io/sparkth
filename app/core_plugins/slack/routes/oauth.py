"""OAuth routes and shared FastAPI dependencies for the Slack TA Bot plugin."""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.core_plugins.slack.config import SlackSettings, get_slack_settings
from app.core_plugins.slack.enums import ConnectionEventType
from app.core_plugins.slack.exceptions import UserAlreadyConnectedError, WorkspaceAlreadyConnectedError
from app.core_plugins.slack.models import SlackConnectionLog
from app.core_plugins.slack.oauth import decode_state, exchange_code_for_tokens, generate_authorization_url
from app.core_plugins.slack.routes.dependencies import require_user_id
from app.core_plugins.slack.service import WorkspaceService, get_workspace_service
from app.core_plugins.slack.types import AuthorizationUrlResponse, ConnectionStatusResponse
from app.lib.db import get_session
from app.lib.log import get_logger

oauth_router: APIRouter = APIRouter()
logger = get_logger(__name__)


def get_slack_credentials() -> SlackSettings:
    """Return validated Slack settings.

    Raises HTTPException 503 if any environmental credential is missing.
    """
    s = get_slack_settings()
    if not s.client_id or not s.client_secret or not s.signing_secret or not s.redirect_uri:
        logger.error(
            "Slack credentials not configured. Set SLACK_CLIENT_ID, "
            "SLACK_CLIENT_SECRET, SLACK_SIGNING_SECRET, SLACK_REDIRECT_URI"
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Slack credentials not configured.")
    return s


@oauth_router.get("/oauth/authorize", response_model=AuthorizationUrlResponse)
def get_authorization_url(user_id: int = Depends(require_user_id)) -> AuthorizationUrlResponse:
    """Return the Slack OAuth install URL."""
    creds = get_slack_credentials()
    url = generate_authorization_url(user_id, creds.client_id, creds.redirect_uri)
    return AuthorizationUrlResponse(url=url)


@oauth_router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    service: WorkspaceService = Depends(get_workspace_service),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle Slack OAuth redirect, persist workspace token."""
    try:
        state_data = decode_state(state)
        user_id = state_data["user_id"]
    except SignatureExpired as exc:
        logger.warning("Slack OAuth state expired for callback request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired. Please try again."
        ) from exc
    except (BadSignature, KeyError, ValueError, TypeError) as exc:
        logger.warning("Invalid Slack OAuth state received: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    creds = get_slack_credentials()

    try:
        token_data = await exchange_code_for_tokens(code, creds.client_id, creds.client_secret, creds.redirect_uri)
    except (ValueError, httpx.HTTPStatusError) as exc:
        logger.error("Slack OAuth code exchange failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange Slack authorization code."
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Network error during Slack OAuth for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not reach Slack. Please try again."
        ) from exc

    try:
        workspace = service.save(
            session,
            user_id,
            token_data["team"]["id"],
            token_data["team"]["name"],
            token_data["access_token"],
            token_data["bot_user_id"],
        )
    except UserAlreadyConnectedError as exc:
        logger.warning("User %s already has an active Slack workspace connected", user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a Slack workspace connected. Disconnect it first before connecting a new one.",
        ) from exc
    except WorkspaceAlreadyConnectedError as exc:
        logger.warning("Slack workspace %s already connected to another account", token_data.get("team", {}).get("id"))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Slack workspace is already connected to another account.",
        ) from exc
    except (KeyError, TypeError) as exc:
        logger.error("Unexpected Slack token response structure for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected response from Slack. Please try again.",
        ) from exc

    try:
        session.add(
            SlackConnectionLog(
                workspace_id=workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.CONNECTED,
                team_name=token_data["team"]["name"],
            )
        )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Failed to log Slack connect event for user %s: %s", user_id, exc)

    return RedirectResponse(url=f"{get_slack_settings().frontend_path}?connected=true")


@oauth_router.delete("/oauth/disconnect")
def disconnect_workspace(
    user_id: int = Depends(require_user_id),
    service: WorkspaceService = Depends(get_workspace_service),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Disconnect the Slack workspace for the current user."""
    workspace = service.get(session, user_id)
    if not workspace:
        logger.warning("Disconnect requested but no workspace found for user %d", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack workspace not connected")

    try:
        session.add(
            SlackConnectionLog(
                workspace_id=workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.DISCONNECTED,
                team_name=workspace.team_name,
            )
        )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Failed to log Slack disconnect event for user %d: %s", user_id, exc)

    service.delete(session, user_id)
    return {"detail": "Slack workspace disconnected successfully"}


@oauth_router.get("/oauth/status", response_model=ConnectionStatusResponse)
def get_connection_status(
    user_id: int = Depends(require_user_id),
    service: WorkspaceService = Depends(get_workspace_service),
    session: Session = Depends(get_session),
) -> ConnectionStatusResponse:
    """Return Slack connection status for the current user."""
    workspace = service.get(session, user_id)
    if not workspace:
        return ConnectionStatusResponse(connected=False)
    return ConnectionStatusResponse(
        connected=True,
        team_name=workspace.team_name,
        team_id=workspace.team_id,
        bot_user_id=workspace.bot_user_id,
        connected_at=workspace.created_at,
    )
