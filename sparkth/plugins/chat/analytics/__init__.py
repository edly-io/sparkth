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
    ChatRagSearchCompleted,
    ChatScopeClassified,
    ChatToolInvoked,
    ChatTurnFailed,
    ScopeVerdict,
    SearchResult,
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
    emit_rag_search_completed,
    executed_tools_from,
    rag_search_event,
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
    "ChatRagSearchCompleted",
    "ChatScopeClassified",
    "ChatToolInvoked",
    "ChatTurnAnalytics",
    "ChatTurnFailed",
    "ExecutedTool",
    "ScopeVerdict",
    "SearchResult",
    "StopPoint",
    "ToolOutcome",
    "TurnFailureCause",
    "as_utc",
    "emit_completion",
    "emit_documents_detached",
    "emit_rag_search_completed",
    "executed_tools_from",
    "rag_search_event",
    "record_turn_failed",
]
