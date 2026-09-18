import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
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
    moodle_authenticate,
    moodle_create_course,
    moodle_create_page,
    moodle_create_quiz,
    moodle_create_section,
    moodle_list_courses,
)

_LOGGER = "sparkth.plugins.moodle.tools"

AUTH = Auth(api_url="https://moodle.example.com", api_token="tok")


def _client_returning(value: Any) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.call_dict = AsyncMock(return_value=value)
    client.call_list = AsyncMock(return_value=value)
    return client


class TestMoodleAuthenticate:
    @pytest.mark.asyncio
    async def test_returns_the_site_and_user(self) -> None:
        client = _client_returning({"sitename": "Sparkth Moodle Dev", "username": "author", "userid": 3})
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result == {"sitename": "Sparkth Moodle Dev", "username": "author", "userid": 3}
        assert client.call_dict.call_args.args[0] == "core_webservice_get_site_info"

    @pytest.mark.asyncio
    async def test_a_rejected_token_becomes_an_error_dict(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(side_effect=AuthenticationError(401, "Invalid token"))
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result["error"]["status_code"] == 401
        assert result["error"]["message"] == "Invalid token"

    @pytest.mark.asyncio
    async def test_a_malformed_response_becomes_an_error_dict_with_a_status_code(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(
            side_effect=ValueError("Expected JSON object from core_webservice_get_site_info, got list")
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result["error"]["status_code"] == 502
        assert "core_webservice_get_site_info" in result["error"]["message"]


class TestMoodleCreateCourse:
    @pytest.mark.asyncio
    async def test_returns_the_created_course(self) -> None:
        client = _client_returning([{"id": 4, "shortname": "intro"}])
        payload = CoursePayload(
            auth=AUTH,
            fullname="Intro",
            shortname="intro",
            categoryid=1,
            summary="<p>About</p>",
            lang="en",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_course(payload)

        assert result == {"course": {"id": 4, "shortname": "intro"}}

    @pytest.mark.asyncio
    async def test_sends_the_course_as_a_single_item_list(self) -> None:
        client = _client_returning([{"id": 4}])
        payload = CoursePayload(
            auth=AUTH,
            fullname="Intro",
            shortname="intro",
            categoryid=1,
            summary="",
            lang="en",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            await moodle_create_course(payload)

        wsfunction, params = client.call_list.call_args.args
        assert wsfunction == "core_course_create_courses"
        assert len(params["courses"]) == 1
        assert params["courses"][0]["fullname"] == "Intro"
        assert "numsections" not in params["courses"][0]

    @pytest.mark.asyncio
    async def test_omits_lang_when_left_at_the_default(self) -> None:
        client = _client_returning([{"id": 4}])
        payload = CoursePayload(auth=AUTH, fullname="Intro", shortname="intro", categoryid=1)
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            await moodle_create_course(payload)

        _, params = client.call_list.call_args.args
        assert params["courses"][0]["lang"] is None

    @pytest.mark.asyncio
    async def test_passes_through_a_supplied_lang(self) -> None:
        client = _client_returning([{"id": 4}])
        payload = CoursePayload(
            auth=AUTH,
            fullname="Intro",
            shortname="intro",
            categoryid=1,
            lang="fr",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            await moodle_create_course(payload)

        _, params = client.call_list.call_args.args
        assert params["courses"][0]["lang"] == "fr"

    @pytest.mark.asyncio
    async def test_authentication_failure_becomes_an_error_dict(self) -> None:
        client = _client_returning(None)
        client.call_list = AsyncMock(side_effect=AuthenticationError(401, "Invalid token"))
        payload = CoursePayload(
            auth=AUTH,
            fullname="Intro",
            shortname="intro",
            categoryid=1,
            summary="",
            lang="en",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_course(payload)

        assert result["error"]["status_code"] == 401
        assert result["error"]["message"] == "Invalid token"

    @pytest.mark.asyncio
    async def test_a_malformed_response_becomes_an_error_dict_with_a_status_code(self) -> None:
        client = _client_returning(None)
        client.call_list = AsyncMock(
            side_effect=ValueError("Expected JSON array from core_course_create_courses, got dict")
        )
        payload = CoursePayload(
            auth=AUTH,
            fullname="Intro",
            shortname="intro",
            categoryid=1,
            summary="",
            lang="en",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_course(payload)

        assert result["error"]["status_code"] == 502
        assert "core_course_create_courses" in result["error"]["message"]


class TestMoodleListCourses:
    @pytest.mark.asyncio
    async def test_returns_only_the_users_own_courses(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(return_value={"userid": 3})
        client.call_list = AsyncMock(return_value=[{"id": 4, "fullname": "Intro"}])
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_list_courses(AUTH)

        assert result == {"courses": [{"id": 4, "fullname": "Intro"}]}

        first, second = client.call_dict.call_args_list[0], client.call_list.call_args_list[0]
        assert first.args[0] == "core_webservice_get_site_info"
        assert second.args == ("core_enrol_get_users_courses", {"userid": 3})

    @pytest.mark.asyncio
    async def test_a_malformed_response_becomes_an_error_dict_with_a_status_code(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(return_value={"userid": 3})
        client.call_list = AsyncMock(
            side_effect=ValueError("Expected JSON array from core_enrol_get_users_courses, got dict")
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_list_courses(AUTH)

        assert result["error"]["status_code"] == 502
        assert "core_enrol_get_users_courses" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_a_site_info_failure_is_reported_under_its_own_operation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(side_effect=AuthenticationError(401, "Invalid token"))
        with (
            caplog.at_level(logging.WARNING, logger=_LOGGER),
            patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client),
        ):
            result = await moodle_list_courses(AUTH)

        assert result["error"]["status_code"] == 401
        assert "core_webservice_get_site_info" in caplog.text
        assert "core_enrol_get_users_courses" not in caplog.text


class TestMoodleCreateSection:
    @pytest.mark.asyncio
    async def test_returns_the_new_section_number(self) -> None:
        client = _client_returning({"id": 6, "sectionnum": 1})
        payload = SectionPayload(auth=AUTH, courseid=4, name="Module 1", summary="<p>i</p>")
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_section(payload)

        assert result == {"id": 6, "sectionnum": 1}
        wsfunction, params = client.call_dict.call_args.args
        assert wsfunction == "local_sparkth_create_section"
        assert params == {"courseid": 4, "name": "Module 1", "summary": "<p>i</p>"}


class TestMoodleCreatePage:
    @pytest.mark.asyncio
    async def test_returns_the_created_module_ids(self) -> None:
        client = _client_returning({"cmid": 9, "instanceid": 2})
        payload = PagePayload(
            auth=AUTH,
            courseid=4,
            sectionnum=1,
            name="Lesson One",
            content="<h2>Hi</h2>",
            intro="",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_page(payload)

        assert result == {"cmid": 9, "instanceid": 2}
        wsfunction, params = client.call_dict.call_args.args
        assert wsfunction == "local_sparkth_create_page"
        assert params["content"] == "<h2>Hi</h2>"

    @pytest.mark.asyncio
    async def test_missing_companion_plugin_becomes_an_error_dict(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(
            side_effect=LMSRequestError(
                Method.POST,
                "local_sparkth_create_page",
                400,
                "Can not find data record in database table external_functions.",
            )
        )
        payload = PagePayload(
            auth=AUTH,
            courseid=4,
            sectionnum=1,
            name="L",
            content="<p>x</p>",
            intro="",
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_page(payload)

        assert result["error"]["status_code"] == 400
        assert "external_functions" in result["error"]["message"]


def _quiz_payload() -> QuizPayload:
    return QuizPayload(
        auth=AUTH,
        courseid=4,
        sectionnum=1,
        name="Section Quiz",
        intro="<p>Check.</p>",
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


class TestMoodleCreateQuiz:
    @pytest.mark.asyncio
    async def test_returns_the_created_quiz(self) -> None:
        client = _client_returning({"cmid": 11, "instanceid": 3, "questioncount": 2})
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_create_quiz(_quiz_payload())

        assert result == {"cmid": 11, "instanceid": 3, "questioncount": 2}

    @pytest.mark.asyncio
    async def test_questions_are_sent_as_plain_dicts(self) -> None:
        client = _client_returning({"cmid": 11, "instanceid": 3, "questioncount": 2})
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            await moodle_create_quiz(_quiz_payload())

        wsfunction, params = client.call_dict.call_args.args
        assert wsfunction == "local_sparkth_create_quiz"
        assert params["questions"][0]["qtype"] == "multichoice"
        assert params["questions"][0]["answers"] == ["3", "4"]
        assert params["questions"][1]["qtype"] == "truefalse"

    def test_an_unsupported_question_type_is_rejected_at_the_boundary(self) -> None:
        with pytest.raises(ValidationError):
            Question(qtype="essay", name="E", questiontext="<p>Discuss.</p>")  # type: ignore[arg-type]
