"""Slack OAuth helpers for the TA Bot plugin."""

import base64
import hashlib
import urllib.parse
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import URLSafeTimedSerializer
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core_plugins.slack.constants import BOT_SCOPES, SLACK_AUTHORIZE_URL, SLACK_TOKEN_URL, STATE_MAX_AGE
from app.core_plugins.slack.models import SlackWorkspace
from app.lib.log import get_logger

logger = get_logger(__name__)


class TokenEncryptionService:
    """Handles Fernet-based symmetric encryption and decryption of Slack bot tokens."""

    def _get_fernet(self) -> Fernet:
        settings = get_settings()
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    def encrypt_token(self, token: str) -> str:
        return self._get_fernet().encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted: str) -> str:
        try:
            return self._get_fernet().decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt Slack bot token") from exc


class OAuthStateManager:
    """Manages CSRF state tokens and authorization URL generation for the Slack OAuth flow."""

    def _get_signer(self) -> URLSafeTimedSerializer:
        settings = get_settings()
        return URLSafeTimedSerializer(settings.SECRET_KEY, salt="slack-oauth-state")

    def generate_state(self, user_id: int) -> str:
        return self._get_signer().dumps({"user_id": user_id})

    def decode_state(self, state: str) -> dict[str, int]:
        data: dict[str, int] = self._get_signer().loads(state, max_age=STATE_MAX_AGE)
        return data

    def generate_authorization_url(self, user_id: int, client_id: str, redirect_uri: str) -> str:
        params = {
            "client_id": client_id,
            "scope": ",".join(BOT_SCOPES),
            "redirect_uri": redirect_uri,
            "state": self.generate_state(user_id),
        }
        return f"{SLACK_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


class WorkspaceRepository:
    """Handles persistence of Slack workspace connections in the database."""

    def __init__(self, cipher: TokenEncryptionService) -> None:
        self._cipher = cipher

    def save(
        self,
        session: Session,
        user_id: int,
        team_id: str,
        team_name: str,
        bot_token: str,
        bot_user_id: str,
    ) -> SlackWorkspace:
        """Upsert — one active workspace per user. Reconnecting overwrites."""
        existing = session.exec(
            select(SlackWorkspace).where(
                SlackWorkspace.user_id == user_id,
                SlackWorkspace.is_deleted == False,  # noqa: E712
            )
        ).first()

        if existing:
            existing.team_id = team_id
            existing.team_name = team_name
            existing.bot_token_encrypted = self._cipher.encrypt_token(bot_token)
            existing.bot_user_id = bot_user_id
            existing.is_active = True
            existing.is_deleted = False
            existing.deleted_at = None
            existing.update_timestamp()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        workspace = SlackWorkspace(
            user_id=user_id,
            team_id=team_id,
            team_name=team_name,
            bot_token_encrypted=self._cipher.encrypt_token(bot_token),
            bot_user_id=bot_user_id,
        )
        session.add(workspace)
        session.commit()
        session.refresh(workspace)
        return workspace

    def get(self, session: Session, user_id: int) -> SlackWorkspace | None:
        return session.exec(
            select(SlackWorkspace).where(
                SlackWorkspace.user_id == user_id,
                SlackWorkspace.is_active == True,  # noqa: E712
                SlackWorkspace.is_deleted == False,  # noqa: E712
            )
        ).first()

    def get_by_team(self, session: Session, team_id: str) -> SlackWorkspace | None:
        return session.exec(
            select(SlackWorkspace).where(
                SlackWorkspace.team_id == team_id,
                SlackWorkspace.is_active == True,  # noqa: E712
                SlackWorkspace.is_deleted == False,  # noqa: E712
            )
        ).first()

    def delete(self, session: Session, user_id: int) -> None:
        workspace = self.get(session, user_id)
        if workspace:
            workspace.soft_delete()
            workspace.is_active = False
            session.add(workspace)
            session.commit()


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange an OAuth code for Slack tokens.

    Raises:
        httpx.HTTPStatusError: If Slack returns a non-2xx response.
        httpx.RequestError: If the request fails due to a network error.
        ValueError: If Slack returns ok=false in the response body.
    """
    async with httpx.AsyncClient() as http:
        response = await http.post(
            SLACK_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    if not data.get("ok"):
        raise ValueError(f"Slack OAuth error: {data.get('error', 'unknown')}")
    return data


# Module-level singletons
_token_cipher = TokenEncryptionService()
_state_manager = OAuthStateManager()
_workspace_repo = WorkspaceRepository(cipher=_token_cipher)


# Module-level backward-compatible functions


def _get_signer() -> URLSafeTimedSerializer:
    return _state_manager._get_signer()


def encrypt_token(token: str) -> str:
    return _token_cipher.encrypt_token(token)


def decrypt_token(encrypted: str) -> str:
    return _token_cipher.decrypt_token(encrypted)


def generate_state(user_id: int) -> str:
    return _state_manager.generate_state(user_id)


def decode_state(state: str) -> dict[str, int]:
    return _state_manager.decode_state(state)


def generate_authorization_url(user_id: int, client_id: str, redirect_uri: str) -> str:
    return _state_manager.generate_authorization_url(user_id, client_id, redirect_uri)


def save_workspace(
    session: Session,
    user_id: int,
    team_id: str,
    team_name: str,
    bot_token: str,
    bot_user_id: str,
) -> SlackWorkspace:
    return _workspace_repo.save(session, user_id, team_id, team_name, bot_token, bot_user_id)


def get_workspace(session: Session, user_id: int) -> SlackWorkspace | None:
    return _workspace_repo.get(session, user_id)


def get_workspace_by_team(session: Session, team_id: str) -> SlackWorkspace | None:
    return _workspace_repo.get_by_team(session, team_id)


def delete_workspace(session: Session, user_id: int) -> None:
    _workspace_repo.delete(session, user_id)
