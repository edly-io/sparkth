"""Slack TA Bot plugin for Sparkth."""

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.enums import ConnectionEventType, ResponseType
from app.core_plugins.slack.events import SlackEventParser
from app.core_plugins.slack.models import BotResponseLog, SlackConnectionLog, SlackWorkspace
from app.core_plugins.slack.oauth import OAuthStateManager, TokenEncryptionService, WorkspaceRepository
from app.core_plugins.slack.plugin import Slack
from app.core_plugins.slack.rag import SlackRAGDispatcher
from app.core_plugins.slack.synthesis import AnswerSynthesizer

__all__ = [
    "AnswerSynthesizer",
    "BotResponseLog",
    "ConnectionEventType",
    "OAuthStateManager",
    "ResponseType",
    "Slack",
    "SlackConfig",
    "SlackConnectionLog",
    "SlackEventParser",
    "SlackRAGDispatcher",
    "SlackWorkspace",
    "TokenEncryptionService",
    "WorkspaceRepository",
]
