"""Analytics event schema: ``assessment.submitted`` (v1).

A representative event that proves the registry + versioning + gateway path. It is
not yet emitted by any producer — producer wiring is a later phase. Server-only by
the inherited default: it must be emitted by trusted server-side callers, never the
HTTP endpoint.
"""

from app.core.analytics.schemas import AnalyticsEventSchema


class AssessmentSubmitted(AnalyticsEventSchema):
    event_type = "assessment.submitted"
    version = 1

    learner_id: str
    competency_id: str
    score: float
    passed: bool
