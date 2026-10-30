"""Analytics events for the chat plugin — instructor course-authoring activity.

Schemas live in :mod:`~sparkth.plugins.compose.analytics.events`, the emission helpers and
scheduling surfaces in :mod:`~sparkth.plugins.compose.analytics.utils`. Both are re-exported
here, which is what every call site imports from.
"""

from sparkth.plugins.compose.analytics.events import (
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
from sparkth.plugins.compose.analytics.utils import (
    AnalyticsAttribution,
    ComposeAttachmentAnalytics,
    ComposeClassifierAnalytics,
    ComposeTurnAnalytics,
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
    "ChatAttachmentUnusable",
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
    "ChatTurnFailed",
    "ComposeAttachmentAnalytics",
    "ComposeClassifierAnalytics",
    "ComposeTurnAnalytics",
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
