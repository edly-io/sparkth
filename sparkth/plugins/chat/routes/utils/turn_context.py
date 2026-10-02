"""The request-scoped facts every step of a chat completion turn reads."""

from dataclasses import dataclass

from fastapi import BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.plugins.chat.analytics import ChatClassifierAnalytics
from sparkth.plugins.chat.config import ChatSettings
from sparkth.plugins.chat.schemas import ChatCompletionRequest
from sparkth.plugins.chat.service import ChatService


@dataclass(frozen=True)
class TurnContext:
    """What a completion turn knows once its AI key is resolved, before any conversation is opened.

    ``model`` already has the request's override applied. ``query_text`` is the last user
    message's text and ``request_attachment_names`` the files uploaded with the message itself:
    those are base64 content rather than Document rows, so their names exist only here.
    """

    request: ChatCompletionRequest
    user_id: int
    provider_name: str
    model: str
    api_key: str
    query_text: str
    request_attachment_names: list[str]
    classifier_analytics: ChatClassifierAnalytics
    session: AsyncSession
    service: ChatService
    config: ChatSettings
    background_tasks: BackgroundTasks
