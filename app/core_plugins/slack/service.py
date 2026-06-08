import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core_plugins.slack.exceptions import UserAlreadyConnectedError, WorkspaceAlreadyConnectedError
from app.core_plugins.slack.models import SlackWorkspace
from app.lib.log import get_logger

logger = get_logger(__name__)


@lru_cache
def _get_fernet() -> Fernet:
    key = hashlib.sha256(get_settings().SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt Slack bot token") from exc


def get_workspace_service() -> "WorkspaceService":
    """FastAPI dependency that returns a WorkspaceService."""
    return WorkspaceService()


class WorkspaceService:
    """Handles persistence of Slack workspace connections in the database."""

    def save(
        self,
        session: Session,
        user_id: int,
        team_id: str,
        team_name: str,
        bot_token: str,
        bot_user_id: str,
    ) -> SlackWorkspace:
        """Persist a new workspace connection. Raises if already connected."""
        workspace = SlackWorkspace(
            user_id=user_id,
            team_id=team_id,
            team_name=team_name,
            bot_token_encrypted=encrypt_token(bot_token),
            bot_user_id=bot_user_id,
        )
        try:
            with session.begin_nested():
                session.add(workspace)
        except IntegrityError:
            existing_for_user = session.exec(
                select(SlackWorkspace).where(
                    SlackWorkspace.user_id == user_id,
                    SlackWorkspace.is_deleted == False,  # noqa: E712
                )
            ).first()
            if existing_for_user:
                raise UserAlreadyConnectedError(user_id)
            existing_for_team = session.exec(
                select(SlackWorkspace).where(
                    SlackWorkspace.team_id == team_id,
                    SlackWorkspace.is_deleted == False,  # noqa: E712
                )
            ).first()
            if existing_for_team:
                raise WorkspaceAlreadyConnectedError(team_id)

            logger.error(
                "Unexpected IntegrityError saving workspace for user=%d team=%s",
                user_id,
                team_id,
                exc_info=True,
            )
            raise

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
