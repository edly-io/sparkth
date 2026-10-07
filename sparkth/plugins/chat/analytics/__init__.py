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
    ToolOutcome,
    TurnFailureCause,
)
from sparkth.plugins.chat.analytics.utils import (
    AnalyticsAttribution,
    ChatAttachmentAnalytics,
    ChatClassifierAnalytics,
    ChatTurnAnalytics,
    ExecutedTool,
    as_utc,
    emit_completion,
    emit_documents_detached,
    executed_tools_from,
    record_turn_failed,
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
    "ExecutedTool",
    "ScopeVerdict",
    "StopPoint",
    "ToolOutcome",
    "TurnFailureCause",
    "as_utc",
    "emit_completion",
    "emit_documents_detached",
    "executed_tools_from",
    "record_turn_failed",
]
