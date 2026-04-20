"""FastAPI routes for the Slack TA Bot plugin."""

import json as _json
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.db import async_engine, get_session
from app.core.logger import get_logger
from app.core_plugins.slack.client import SlackClient
from app.core_plugins.slack.config import SlackBotConfig
from app.core_plugins.slack.events import extract_question, is_greeting, should_handle_event
from app.core_plugins.slack.exceptions import SlackSignatureError
from app.core_plugins.slack.models import BotResponseLog
from app.core_plugins.slack.oauth import (
    decode_state,
    decrypt_token,
    delete_workspace,
    exchange_code_for_tokens,
    generate_authorization_url,
    get_workspace,
    get_workspace_by_team,
    save_workspace,
)
from app.core_plugins.slack.rag import answer_question
from app.core_plugins.slack.types import (
    AuthorizationUrlResponse,
    BotResponseLogItem,
    ConnectionStatusResponse,
    LogsResponse,
)
from app.models.user import User
from app.services.plugin import PluginService

router: APIRouter = APIRouter()
logger = get_logger(__name__)


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id


def get_slack_credentials() -> tuple[str, str, str, str]:
    """
    Return (client_id, client_secret, redirect_uri, signing_secret).

    Raises HTTPException 503 if any environmental credential is missing.
    """
    s = get_settings()
    if not s.SLACK_CLIENT_ID or not s.SLACK_CLIENT_SECRET or not s.SLACK_SIGNING_SECRET or not s.SLACK_REDIRECT_URI:
        logger.error(
            "Slack credentials not configured. Set SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_SIGNING_SECRET, SLACK_REDIRECT_URI"
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Slack credentials not configured.")
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
    except SignatureExpired as exc:
        logger.warning("Slack OAuth state expired for callback request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired. Please try again."
        ) from exc
    except (BadSignature, KeyError, ValueError, TypeError) as exc:
        logger.warning("Invalid Slack OAuth state received: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    client_id, client_secret, redirect_uri, _ = get_slack_credentials()

    try:
        token_data = await exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
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
        save_workspace(
            session,
            user_id=user_id,
            team_id=token_data["team"]["id"],
            team_name=token_data["team"]["name"],
            bot_token=token_data["access_token"],
            bot_user_id=token_data["bot_user_id"],
        )
    except (KeyError, TypeError) as exc:
        logger.error("Unexpected Slack token response structure for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected response from Slack. Please try again.",
        ) from exc

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


async def _dispatch_event(
    workspace_id: int,
    user_id: int,
    bot_token_encrypted: str,
    bot_user_id: str,
    event: dict[str, Any],
) -> None:
    """Background coroutine: embed question, call RAG, post reply, log result."""
    config = SlackBotConfig()
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        try:
            plugin_map = await PluginService().get_user_plugin_map(session, user_id)
            user_plugin = plugin_map.get("slack")
            if user_plugin and user_plugin.config:
                config = SlackBotConfig(**user_plugin.config)
        except (SQLAlchemyError, ValidationError) as exc:
            logger.warning(
                "Could not load SlackBotConfig for user %s, using defaults: %s",
                user_id,
                exc,
            )

        question = extract_question(event.get("text", ""), bot_user_id)
        channel = event.get("channel", "")
        slack_user = event.get("user", "")
        thread_ts: str | None = event.get("thread_ts") or event.get("ts")

        if is_greeting(question):
            answer = config.greeting_message
            rag_matched = False
        else:
            try:
                answer, rag_matched = await answer_question(session, user_id, question, config)
            except (SQLAlchemyError, LangChainException, OSError) as exc:
                logger.error("RAG dispatch failed for workspace %s: %s", workspace_id, exc)
                answer = config.fallback_message
                rag_matched = False
                await session.rollback()

        try:
            bot_token = decrypt_token(bot_token_encrypted)
            async with SlackClient(bot_token) as slack:
                resp = await slack.post_message(channel=channel, text=answer, thread_ts=thread_ts)
            posted_ts: str = resp.get("ts", "")
        except (ValueError, httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error(
                "Slack delivery failed for workspace %s (%s): %s",
                workspace_id,
                type(exc).__name__,
                exc,
            )
            return

        try:
            session.add(
                BotResponseLog(
                    workspace_id=workspace_id,
                    slack_channel=channel,
                    slack_user=slack_user,
                    slack_ts=posted_ts,
                    question=question,
                    answer=answer,
                    rag_matched=rag_matched,
                )
            )
            await session.commit()
        except SQLAlchemyError as exc:
            logger.error("Failed to log bot response for workspace %s: %s", workspace_id, exc)


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Receive Slack Events API payloads. Returns 200 immediately."""
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    slack_sig = request.headers.get("X-Slack-Signature", "")

    settings = get_settings()
    if settings.SLACK_SIGNING_SECRET:
        try:
            SlackClient.verify_signature(settings.SLACK_SIGNING_SECRET, timestamp, raw_body, slack_sig)
        except SlackSignatureError as exc:
            logger.warning("Slack signature verification failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Slack signature verification failed."
            ) from exc
    else:
        logger.warning("SLACK_SIGNING_SECRET is empty — skipping signature verification")

    try:
        payload: dict[str, Any] = _json.loads(raw_body)
    except _json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in Slack event payload: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        if challenge is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing challenge field")
        return {"challenge": challenge}

    if payload.get("type") == "event_callback":
        team_id: str = payload.get("team_id", "")
        event: dict[str, Any] = payload.get("event", {})
        workspace = get_workspace_by_team(session, team_id)
        if workspace and should_handle_event(event, workspace.bot_user_id):
            background_tasks.add_task(
                _dispatch_event,
                workspace_id=workspace.id,  # type: ignore[arg-type]
                user_id=workspace.user_id,
                bot_token_encrypted=workspace.bot_token_encrypted,
                bot_user_id=workspace.bot_user_id,
                event=event,
            )

    return {"ok": "true"}


@router.get("/logs", response_model=LogsResponse)
def get_response_logs(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> LogsResponse:
    """Return recent TA Bot response logs for the authenticated user."""
    workspace = get_workspace(session, user_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack workspace not connected")

    rows = session.exec(
        select(BotResponseLog)
        .where(col(BotResponseLog.workspace_id) == workspace.id)
        .order_by(col(BotResponseLog.created_at).desc())
        .limit(limit)
    ).all()

    items = [
        BotResponseLogItem(
            id=row.id,  # type: ignore[arg-type]
            slack_channel=row.slack_channel,
            slack_user=row.slack_user,
            question=row.question,
            answer=row.answer,
            rag_matched=row.rag_matched,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return LogsResponse(items=items, total=len(items))
