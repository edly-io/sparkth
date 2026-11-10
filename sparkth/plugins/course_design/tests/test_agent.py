import re

import pytest

from sparkth.plugins.course_design.agent import COURSE_DESIGN

LMS_TERMS = re.compile(r"\b(publish\w*|lms|canvas|moodle|open edx)\b", re.IGNORECASE)


@pytest.mark.parametrize("text", [COURSE_DESIGN.prompt, COURSE_DESIGN.description], ids=["prompt", "description"])
def test_course_design_text_has_no_lms_operations(text: str) -> None:
    """Publishing and managing courses on an LMS is Compose's work, not the course designer's."""
    assert not LMS_TERMS.search(text)


def test_course_design_description_keeps_the_written_assessment_boundary() -> None:
    """A written quiz stays course design's; an interactive activity is another agent's."""
    assert "Creating written educational assessments" in COURSE_DESIGN.description
