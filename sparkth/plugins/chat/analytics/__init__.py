"""Analytics events for the chat plugin — instructor course-authoring activity.

Schemas live in :mod:`~sparkth.plugins.chat.analytics.events`, the emission helpers and
scheduling surfaces in :mod:`~sparkth.plugins.chat.analytics.utils`. Both are re-exported
here, which is what every call site imports from.
"""

from sparkth.plugins.chat.analytics.events import (
    ChatAttachmentUnusable,
    ChatCompletionServed,
    ChatConversationStarted,
    ChatDocumentAttached,
    ChatDocumentDetached,
    ChatDocumentsSkipped,
    ChatMessageSent,
    ChatRagSearchClassified,
    ChatScopeClassified,
    ChatToolInvoked,
    ChatTurnFailed,
    ScopeVerdict,
    StopPoint,
    TurnFailureCause,
)
from sparkth.plugins.chat.analytics.utils import (
    AnalyticsAttribution,
    ChatAttachmentAnalytics,
    ChatClassifierAnalytics,
    ChatTurnAnalytics,
    as_utc,
    emit_completion,
    emit_documents_detached,
    record_turn_failed,
    tool_names,
)

__all__ = [
    "AnalyticsAttribution",
    "ChatAttachmentAnalytics",
    "ChatAttachmentUnusable",
    "ChatClassifierAnalytics",
    "ChatCompletionServed",
    "ChatConversationStarted",
    "ChatDocumentAttached",
    "ChatDocumentDetached",
    "ChatDocumentsSkipped",
    "ChatMessageSent",
    "ChatRagSearchClassified",
    "ChatScopeClassified",
    "ChatToolInvoked",
    "ChatTurnAnalytics",
    "ChatTurnFailed",
    "ScopeVerdict",
    "StopPoint",
    "TurnFailureCause",
    "as_utc",
    "emit_completion",
    "emit_documents_detached",
    "record_turn_failed",
    "tool_names",
]
