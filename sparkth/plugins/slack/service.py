import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import AuditChange, AuditOutcome, AuditTarget
from sparkth.lib.log import get_logger
from sparkth.lib.settings import get_settings
from sparkth.plugins.slack.audit import SLACK_WORKSPACE_TARGET, SlackConnectedAuditEvent, SlackDisconnectedAuditEvent
from sparkth.plugins.slack.exceptions import UserAlreadyConnectedError, WorkspaceAlreadyConnectedError
from sparkth.plugins.slack.models import SlackWorkspace

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


def _audit_snapshot(workspace: SlackWorkspace) -> dict[str, str]:
    return {"team_id": workspace.team_id, "bot_user_id": workspace.bot_user_id}


def get_workspace_service() -> "WorkspaceService":
    """FastAPI dependency that returns a WorkspaceService."""
    return WorkspaceService()


class WorkspaceService:
    """Handles persistence of Slack workspace connections in the database."""

    async def save(
        self,
        session: AsyncSession,
        user_id: int,
        team_id: str,
        team_name: str,
        bot_token: str,
        bot_user_id: str,
    ) -> SlackWorkspace:
        """Persist a new workspace connection and record ``slack.connected``.

        The audit row commits atomically with the workspace (fail-closed).

        Raises:
            UserAlreadyConnectedError: The user already has an active workspace.
            WorkspaceAlreadyConnectedError: The team is connected to another user.
        """
        workspace = SlackWorkspace(
            user_id=user_id,
            team_id=team_id,
            team_name=team_name,
            bot_token_encrypted=encrypt_token(bot_token),
            bot_user_id=bot_user_id,
        )
        try:
            async with session.begin_nested():
                session.add(workspace)
                await session.flush()
                await record_event(
                    session,
                    SlackConnectedAuditEvent(
                        outcome=AuditOutcome.SUCCESS,
                        target=AuditTarget(type=SLACK_WORKSPACE_TARGET, id=str(workspace.id)),
                        change=AuditChange(new=_audit_snapshot(workspace)),
                    ),
                )
        except IntegrityError:
            existing_for_user = (
                await session.exec(
                    select(SlackWorkspace).where(
                        SlackWorkspace.user_id == user_id,
                        SlackWorkspace.is_deleted == False,  # noqa: E712
                    )
                )
            ).first()
            if existing_for_user:
                raise UserAlreadyConnectedError(user_id)
            existing_for_team = (
                await session.exec(
                    select(SlackWorkspace).where(
                        SlackWorkspace.team_id == team_id,
                        SlackWorkspace.is_deleted == False,  # noqa: E712
                    )
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

        await session.commit()
        await session.refresh(workspace)
        return workspace

    async def get(self, session: AsyncSession, user_id: int) -> SlackWorkspace | None:
        return (
            await session.exec(
                select(SlackWorkspace).where(
                    SlackWorkspace.user_id == user_id,
                    SlackWorkspace.is_active == True,  # noqa: E712
                    SlackWorkspace.is_deleted == False,  # noqa: E712
                )
            )
        ).first()

    async def get_by_team(self, session: AsyncSession, team_id: str) -> SlackWorkspace | None:
        return (
            await session.exec(
                select(SlackWorkspace).where(
                    SlackWorkspace.team_id == team_id,
                    SlackWorkspace.is_active == True,  # noqa: E712
                    SlackWorkspace.is_deleted == False,  # noqa: E712
                )
            )
        ).first()

    async def delete(self, session: AsyncSession, user_id: int) -> None:
        """Soft-delete the user's active workspace and record ``slack.disconnected``.

        The audit row commits atomically with the deletion (fail-closed); a user
        with no active workspace is a no-op that records nothing.
        """
        workspace = await self.get(session, user_id)
        if workspace:
            workspace.soft_delete()
            workspace.is_active = False
            session.add(workspace)
            await record_event(
                session,
                SlackDisconnectedAuditEvent(
                    outcome=AuditOutcome.SUCCESS,
                    target=AuditTarget(type=SLACK_WORKSPACE_TARGET, id=str(workspace.id)),
                    change=AuditChange(old=_audit_snapshot(workspace)),
                ),
            )
            await session.commit()
