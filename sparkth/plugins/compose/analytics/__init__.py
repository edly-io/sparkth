"""Analytics events for the compose plugin — instructor course-authoring activity.

Schemas live in :mod:`~sparkth.plugins.compose.analytics.events`, the emission helpers and
scheduling surfaces in :mod:`~sparkth.plugins.compose.analytics.utils`. Both are re-exported
here, which is what every call site imports from.
"""

from sparkth.plugins.compose.analytics.events import (
    ComposeAttachmentUnusable,
    ComposeCompletionServed,
    ComposeConversationStarted,
    ComposeDocumentAttached,
    ComposeDocumentDetached,
    ComposeDocumentsSkipped,
    ComposeMessageSent,
    ComposeRagSearchClassified,
    ComposeRagSearchCompleted,
    ComposeScopeClassified,
    ComposeToolInvoked,
    ComposeTurnFailed,
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
    "ComposeAttachmentAnalytics",
    "ComposeAttachmentUnusable",
    "ComposeClassifierAnalytics",
    "ComposeCompletionServed",
    "ComposeConversationStarted",
    "ComposeDocumentAttached",
    "ComposeDocumentDetached",
    "ComposeDocumentsSkipped",
    "ComposeMessageSent",
    "ComposeRagSearchClassified",
    "ComposeRagSearchCompleted",
    "ComposeScopeClassified",
    "ComposeToolInvoked",
    "ComposeTurnAnalytics",
    "ComposeTurnFailed",
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
