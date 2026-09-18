"""End-to-end publish against a real Moodle.

Skipped unless MOODLE_TEST_URL and MOODLE_TEST_TOKEN are set. Unlike the pg lane,
the target also needs the local_sparkth plugin installed and its functions exposed
in a web service — no environment variable can supply that.
"""

import os
import uuid

import pytest

from sparkth.plugins.moodle.enums import QuestionType
from sparkth.plugins.moodle.schemas import (
    Auth,
    CoursePayload,
    PagePayload,
    Question,
    QuizPayload,
    SectionPayload,
)
from sparkth.plugins.moodle.tools import (
    moodle_create_course,
    moodle_create_page,
    moodle_create_quiz,
    moodle_create_section,
)

MOODLE_URL = os.getenv("MOODLE_TEST_URL", "")
MOODLE_TOKEN = os.getenv("MOODLE_TEST_TOKEN", "")

pytestmark = [
    pytest.mark.moodle,
    pytest.mark.skipif(
        not (MOODLE_URL and MOODLE_TOKEN),
        reason="set MOODLE_TEST_URL and MOODLE_TEST_TOKEN to run against a real Moodle",
    ),
]


@pytest.mark.asyncio
async def test_publishes_a_whole_course() -> None:
    auth = Auth(api_url=MOODLE_URL, api_token=MOODLE_TOKEN)
    suffix = uuid.uuid4().hex[:8]

    course = await moodle_create_course(
        CoursePayload(
            auth=auth,
            fullname=f"E2E {suffix}",
            shortname=f"e2e{suffix}",
            categoryid=1,
            summary="<p>End to end.</p>",
            lang="",
        )
    )
    assert "error" not in course
    courseid = course["course"]["id"]

    section = await moodle_create_section(
        SectionPayload(auth=auth, courseid=courseid, name="Module 1", summary="<p>i</p>")
    )
    assert section["sectionnum"] == 1

    page = await moodle_create_page(
        PagePayload(
            auth=auth,
            courseid=courseid,
            sectionnum=1,
            name="Lesson One",
            content="<h2>Hello</h2><p>Body copy.</p>",
            intro="",
        )
    )
    assert page["cmid"] > 0

    quiz = await moodle_create_quiz(
        QuizPayload(
            auth=auth,
            courseid=courseid,
            sectionnum=1,
            name="Section Quiz",
            intro="",
            questions=[
                Question(
                    qtype=QuestionType.MULTICHOICE,
                    name="Q1",
                    questiontext="<p>What is 2+2?</p>",
                    answers=["3", "4"],
                    correctindex=1,
                ),
                Question(
                    qtype=QuestionType.TRUEFALSE,
                    name="Q2",
                    questiontext="<p>The sky is blue.</p>",
                    correcttrue=True,
                ),
            ],
        )
    )
    assert quiz["questioncount"] == 2
