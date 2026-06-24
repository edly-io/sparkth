"""Analytics event schema: ``assessment.submitted`` (v1).

A representative event that proves the registry + versioning + gateway path. It is
not yet emitted by any producer — producer wiring is a later phase.
"""

from pydantic import BaseModel


class AssessmentSubmitted(BaseModel):
    learner_id: str
    competency_id: str
    score: float
    passed: bool
