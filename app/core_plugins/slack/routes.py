"""FastAPI routes for the Slack TA Bot plugin."""

import asyncio
import json as _json
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.cache import get_cache_service
from app.core.config import get_settings
from app.core.db import async_engine, get_async_session, get_session
from app.core.encryption import get_encryption_service
from app.core.logger import get_logger
from app.core_plugins.slack.client import SlackClient
from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.constants import AI_KEY_UNAVAILABLE_MESSAGE, NO_AI_KEY_MESSAGE
from app.core_plugins.slack.events import extract_question, is_greeting, should_handle_event
from app.core_plugins.slack.exceptions import SlackSignatureError
from app.core_plugins.slack.models import BotResponseLog, ConnectionEventType, ResponseType, SlackConnectionLog
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
from app.core_plugins.slack.rag import _RETRIEVAL_ERROR_MESSAGE, answer_question
from app.core_plugins.slack.synthesis import SYNTHESIS_SYSTEM_PROMPT
from app.core_plugins.slack.types import (
    AuthorizationUrlResponse,
    BotResponseLogItem,
    ConnectionLogItem,
    ConnectionStatusResponse,
    LogItem,
    LogsResponse,
    RagSourcesResponse,
)
from app.llm.providers import BaseChatProvider, get_provider
from app.llm.service import LLMConfigService
from app.models.user import User
from app.rag.store import VectorStoreService
from app.services.plugin import PluginService

router: APIRouter = APIRouter()
logger = get_logger(__name__)

SLACK_FRONTEND_PATH = "/dashboard/slack"


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
        workspace = save_workspace(
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

    # Log the connection event
    try:
        session.add(
            SlackConnectionLog(
                workspace_id=workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.connected,
                team_name=token_data["team"]["name"],
            )
        )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Failed to log Slack connect event for user %s: %s", user_id, exc)

    return RedirectResponse(url=f"{SLACK_FRONTEND_PATH}?connected=true")


@router.delete("/oauth/disconnect")
def disconnect_workspace(
    user_id: int = Depends(require_user_id),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Disconnect the Slack workspace for the current user."""
    workspace = get_workspace(session, user_id)
    if not workspace:
        logger.warning("Disconnect requested but no workspace found for user %d", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack workspace not connected")

    try:
        session.add(
            SlackConnectionLog(
                workspace_id=workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.disconnected,
                team_name=workspace.team_name,
            )
        )
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("Failed to log Slack disconnect event for user %d: %s", user_id, exc)

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


async def _build_llm_provider(
    session: AsyncSession,
    user_id: int,
    config_id: int,
    temperature: float,
    model_override: str | None = None,
) -> BaseChatProvider | None:
    """Resolve the user's LLMConfig and build a chat provider for synthesis.

    Returns None if the config cannot be resolved or the provider cannot be built.
    `model_override`, if provided, takes precedence over the LLMConfig's model.
    """
    try:
        settings = get_settings()
        llm_service = LLMConfigService(
            encryption=get_encryption_service(settings.LLM_ENCRYPTION_KEY),
            cache=get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL),
        )
    except (ValidationError, ValueError) as exc:
        logger.error("Failed to initialise LLM service for user %d: %s", user_id, exc)
        return None

    try:
        llm_config, api_key = await llm_service.resolve(
            session=session,
            user_id=user_id,
            config_id=config_id,
        )

        return get_provider(
            provider_name=llm_config.provider,
            api_key=api_key,
            model=model_override or llm_config.model,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            temperature=temperature,
        )
    except (ValueError, SQLAlchemyError) as exc:
        logger.warning(
            "Could not resolve LLM config %s for user %d — synthesis disabled: %s",
            config_id,
            user_id,
            exc,
        )
        return None


async def _post_slack_message(
    bot_token_encrypted: str,
    channel: str,
    text: str,
    thread_ts: str | None,
    workspace_id: int,
) -> str | None:
    """Decrypt token, post a message, return the posted ts or None on failure."""
    try:
        bot_token = decrypt_token(bot_token_encrypted)
        async with SlackClient(bot_token) as slack:
            resp = await slack.post_message(channel=channel, text=text, thread_ts=thread_ts)
        return str(resp.get("ts", ""))
    except (ValueError, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.error(
            "Slack delivery failed for workspace %s (%s): %s",
            workspace_id,
            type(exc).__name__,
            exc,
        )
        return None


async def _resolve_names(
    bot_token_encrypted: str,
    slack_user: str,
    channel: str,
) -> tuple[str | None, str | None]:
    """Resolve Slack user and channel display names. Returns (None, None) on any failure."""
    try:
        bot_token = decrypt_token(bot_token_encrypted)
        async with SlackClient(bot_token) as slack:
            user_name, channel_name = await asyncio.gather(
                slack.get_user_display_name(slack_user),
                slack.get_channel_name(channel),
            )
        return user_name, channel_name
    except (ValueError, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("Name resolution failed for user %s channel %s: %s", slack_user, channel, exc)
        return None, None


async def _log_response(
    session: AsyncSession,
    *,
    workspace_id: int,
    channel: str,
    slack_user: str,
    posted_ts: str,
    question: str,
    answer: str,
    rag_matched: bool,
    response_type: ResponseType,
    slack_user_name: str | None,
    slack_channel_name: str | None,
) -> None:
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
                response_type=response_type,
                slack_user_name=slack_user_name,
                slack_channel_name=slack_channel_name,
            )
        )
        await session.commit()
    except SQLAlchemyError as exc:
        logger.error("Failed to log bot response for workspace %s: %s", workspace_id, exc)


async def _reply_and_log(
    session: AsyncSession,
    *,
    reply: str,
    response_type: ResponseType,
    workspace_id: int,
    channel: str,
    slack_user: str,
    thread_ts: str | None,
    bot_token_encrypted: str,
    question: str,
    slack_user_name: str | None,
    slack_channel_name: str | None,
) -> None:
    posted_ts = await _post_slack_message(bot_token_encrypted, channel, reply, thread_ts, workspace_id)
    if posted_ts is not None:
        await _log_response(
            session,
            workspace_id=workspace_id,
            channel=channel,
            slack_user=slack_user,
            posted_ts=posted_ts,
            question=question,
            answer=reply,
            rag_matched=False,
            response_type=response_type,
            slack_user_name=slack_user_name,
            slack_channel_name=slack_channel_name,
        )


async def _dispatch_event(
    workspace_id: int,
    user_id: int,
    bot_token_encrypted: str,
    bot_user_id: str,
    event: dict[str, Any],
) -> None:
    """Background coroutine: validate plugin, embed question, call RAG, post reply, log result."""
    question = extract_question(event.get("text", ""), bot_user_id)
    channel = event.get("channel", "")
    slack_user = event.get("user", "")
    thread_ts: str | None = event.get("thread_ts") or event.get("ts")

    slack_user_name, slack_channel_name = await _resolve_names(bot_token_encrypted, slack_user, channel)

    common = dict(
        workspace_id=workspace_id,
        channel=channel,
        slack_user=slack_user,
        thread_ts=thread_ts,
        bot_token_encrypted=bot_token_encrypted,
        question=question,
        slack_user_name=slack_user_name,
        slack_channel_name=slack_channel_name,
    )

    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        try:
            plugin_map = await PluginService().get_user_plugin_map(session, user_id)
        except SQLAlchemyError as exc:
            logger.error("Failed to load plugin map for user %d: %s", user_id, exc)
            return

        user_plugin = plugin_map.get("slack")
        if not user_plugin:
            logger.info("Slack plugin not configured for user %d", user_id)
            await _reply_and_log(
                session,
                reply="The TA Bot hasn't been set up by your instructor yet. Please check back later.",
                response_type=ResponseType.plugin_disabled,
                **common,
            )
            return

        if not user_plugin.enabled:
            logger.info("Slack plugin disabled for user %d", user_id)
            await _reply_and_log(
                session,
                reply="The TA Bot is currently disabled by your instructor.",
                response_type=ResponseType.plugin_disabled,
                **common,
            )
            return

        if not user_plugin.config:
            logger.warning("Slack plugin config empty for user %d", user_id)
            await _reply_and_log(
                session,
                reply="The TA Bot configuration is incomplete. Please contact your instructor.",
                response_type=ResponseType.config_incomplete,
                **common,
            )
            return

        try:
            config = SlackConfig(**user_plugin.config)
        except ValidationError as exc:
            logger.warning("Invalid SlackConfig for user %d: %s", user_id, exc)
            await _reply_and_log(
                session,
                reply="The TA Bot configuration is invalid. Please contact your instructor.",
                response_type=ResponseType.config_incomplete,
                **common,
            )
            return

        answer: str
        rag_matched: bool
        response_type: ResponseType

        if is_greeting(question):
            answer = config.greeting_message
            rag_matched = False
            response_type = ResponseType.greeting
        else:
            if config.llm_config_id is None:
                logger.warning(
                    "Slack agentic RAG disabled for workspace %s: no AI key configured",
                    workspace_id,
                )
                answer = NO_AI_KEY_MESSAGE
                rag_matched = False
                response_type = ResponseType.config_incomplete
            else:
                llm_provider = await _build_llm_provider(
                    session,
                    user_id,
                    config.llm_config_id,
                    config.llm_temperature,
                    model_override=config.llm_model_override,
                )

                if llm_provider is None:
                    logger.warning(
                        "Slack agentic RAG disabled for workspace %s: AI key could not be resolved",
                        workspace_id,
                    )
                    answer = AI_KEY_UNAVAILABLE_MESSAGE
                    rag_matched = False
                    response_type = ResponseType.config_incomplete
                else:
                    agent_llm = llm_provider.create_llm()

                    try:
                        answer, response_type = await answer_question(
                            session=session,
                            user_id=user_id,
                            question=question,
                            config=config,
                            agent_llm=agent_llm,
                            llm_provider=llm_provider,
                        )
                        rag_matched = response_type == ResponseType.rag_match
                    except (SQLAlchemyError, LangChainException, OSError) as exc:
                        logger.error("RAG dispatch failed for workspace %s: %s", workspace_id, exc)
                        answer = _RETRIEVAL_ERROR_MESSAGE
                        rag_matched = False
                        response_type = ResponseType.retrieval_error
                        await session.rollback()

        posted_ts = await _post_slack_message(bot_token_encrypted, channel, answer, thread_ts, workspace_id)
        if posted_ts is None:
            return

        await _log_response(
            session,
            workspace_id=workspace_id,
            channel=channel,
            slack_user=slack_user,
            posted_ts=posted_ts,
            question=question,
            answer=answer,
            rag_matched=rag_matched,
            response_type=response_type,
            slack_user_name=slack_user_name,
            slack_channel_name=slack_channel_name,
        )


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
            logger.warning("Slack url_verification payload missing 'challenge' field")
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
    cursor: str | None = Query(default=None),
    since_id: int | None = Query(default=None, ge=0),
) -> LogsResponse:
    """Return TA Bot response logs (messages + connection events) with cursor + since pagination."""
    if cursor is not None and since_id is not None:
        logger.warning("GET /logs called with both cursor and since_id for user %d", user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination parameters: only one pagination strategy may be used at a time.",
        )

    workspace = get_workspace(session, user_id)
    if not workspace:
        logger.warning("GET /logs: no Slack workspace found for user %d", user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack workspace not connected")

    # since_id path: message logs only, used for polling
    if since_id is not None:
        stmt = (
            select(BotResponseLog)
            .where(col(BotResponseLog.workspace_id) == workspace.id)
            .where(col(BotResponseLog.id) > since_id)
            .order_by(col(BotResponseLog.id).asc())
            .limit(limit + 1)
        )
        rows = session.exec(stmt).all()
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        items: list[LogItem] = [_to_message_item(r) for r in rows]
        next_cursor_val = None
        return LogsResponse(items=items, total=len(items), next_cursor=next_cursor_val, has_more=has_more)

    # Merged stream: messages + connection events, composite cursor "{ts}|{id}|{type}"
    # Messages sort before connections at equal timestamps (stable tiebreak).
    cursor_dt: datetime | None = None
    cursor_id: int | None = None
    cursor_type: str | None = None
    if cursor is not None:
        try:
            parts = cursor.split("|")
            if len(parts) != 3:
                raise ValueError("expected 3 pipe-separated parts")
            cursor_ts_str, cursor_id_str, cursor_type = parts
            cursor_dt = datetime.fromisoformat(cursor_ts_str)
            if cursor_dt.tzinfo is None:
                cursor_dt = cursor_dt.replace(tzinfo=timezone.utc)
            cursor_id = int(cursor_id_str)
            if cursor_type not in ("message", "connection"):
                raise ValueError(f"unknown type {cursor_type!r}")
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format.",
            ) from exc

    msg_stmt = (
        select(BotResponseLog)
        .where(col(BotResponseLog.workspace_id) == workspace.id)
        .order_by(col(BotResponseLog.created_at).desc(), col(BotResponseLog.id).desc())
        .limit(limit + 1)
    )
    if cursor_dt is not None and cursor_id is not None and cursor_type is not None:
        if cursor_type == "message":
            msg_stmt = msg_stmt.where(
                or_(
                    col(BotResponseLog.created_at) < cursor_dt,
                    and_(col(BotResponseLog.created_at) == cursor_dt, col(BotResponseLog.id) < cursor_id),
                )
            )
        else:
            # cursor is a connection; messages at cursor_dt precede it, so exclude them too
            msg_stmt = msg_stmt.where(col(BotResponseLog.created_at) < cursor_dt)

    conn_stmt = (
        select(SlackConnectionLog)
        .where(col(SlackConnectionLog.workspace_id) == workspace.id)
        .order_by(col(SlackConnectionLog.created_at).desc(), col(SlackConnectionLog.id).desc())
        .limit(limit + 1)
    )
    if cursor_dt is not None and cursor_id is not None and cursor_type is not None:
        if cursor_type == "connection":
            conn_stmt = conn_stmt.where(
                or_(
                    col(SlackConnectionLog.created_at) < cursor_dt,
                    and_(col(SlackConnectionLog.created_at) == cursor_dt, col(SlackConnectionLog.id) < cursor_id),
                )
            )
        else:
            # cursor is a message; connections at cursor_dt sort after it, so include them
            conn_stmt = conn_stmt.where(col(SlackConnectionLog.created_at) <= cursor_dt)

    msg_rows = session.exec(msg_stmt).all()
    conn_rows = session.exec(conn_stmt).all()

    all_items: list[LogItem] = [_to_message_item(r) for r in msg_rows] + [_to_connection_item(r) for r in conn_rows]
    # Newest first; messages precede connections at equal timestamps (stable tiebreak).
    all_items.sort(
        key=lambda x: (x.created_at, x.id, 0 if x.type == "connection" else 1),
        reverse=True,
    )

    has_more = len(all_items) > limit
    if has_more:
        all_items = all_items[:limit]

    if all_items:
        last = all_items[-1]
        next_cursor_val = f"{last.created_at.isoformat()}|{last.id}|{last.type}"
    else:
        next_cursor_val = None
    return LogsResponse(items=all_items, total=len(all_items), next_cursor=next_cursor_val, has_more=has_more)


def _to_message_item(row: BotResponseLog) -> BotResponseLogItem:
    return BotResponseLogItem(
        id=row.id,  # type: ignore[arg-type]
        slack_channel=row.slack_channel,
        slack_user=row.slack_user,
        slack_user_name=row.slack_user_name,
        slack_channel_name=row.slack_channel_name,
        question=row.question,
        answer=row.answer,
        rag_matched=row.rag_matched,
        response_type=row.response_type,
        created_at=row.created_at,
    )


def _to_connection_item(row: SlackConnectionLog) -> ConnectionLogItem:
    return ConnectionLogItem(
        id=row.id,  # type: ignore[arg-type]
        event_type=row.event_type,
        team_name=row.team_name,
        created_at=row.created_at,
    )


@router.get("/rag/sources", response_model=RagSourcesResponse)
async def list_rag_sources(
    user_id: int = Depends(require_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> RagSourcesResponse:
    """Return the distinct RAG source names available to the current user."""
    store = VectorStoreService()
    try:
        sources = await store.get_sources(session=session, user_id=user_id)
    except SQLAlchemyError as exc:
        logger.error("Failed to fetch RAG sources for user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve RAG sources.",
        ) from exc
    return RagSourcesResponse(sources=sources)
