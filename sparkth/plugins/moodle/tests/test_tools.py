from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from sparkth.lib.exceptions import AuthenticationError
from sparkth.plugins.moodle.schemas import Auth, CoursePayload
from sparkth.plugins.moodle.tools import moodle_authenticate, moodle_create_course, moodle_list_courses

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
        client = _client_returning({"sitename": "Sparkth Moodle Dev", "username": "author"})
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result == {"sitename": "Sparkth Moodle Dev", "username": "author"}
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
        assert params["courses"][0]["fullname"] == "Intro"

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
