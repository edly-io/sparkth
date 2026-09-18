from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.plugins.moodle.client import MoodleClient, flatten_ws_params


class TestFlattenWsParams:
    def test_flat_scalars_keep_their_names(self) -> None:
        assert flatten_ws_params({"courseid": 3, "name": "Module 1"}) == {
            "courseid": "3",
            "name": "Module 1",
        }

    def test_list_of_dicts_uses_bracketed_indices(self) -> None:
        assert flatten_ws_params({"courses": [{"fullname": "Intro", "categoryid": 1}]}) == {
            "courses[0][fullname]": "Intro",
            "courses[0][categoryid]": "1",
        }

    def test_nested_lists_inside_dicts_inside_lists(self) -> None:
        params = {"questions": [{"name": "Q1", "answers": ["3", "4"]}]}
        assert flatten_ws_params(params) == {
            "questions[0][name]": "Q1",
            "questions[0][answers][0]": "3",
            "questions[0][answers][1]": "4",
        }

    def test_booleans_become_one_and_zero(self) -> None:
        assert flatten_ws_params({"visible": True, "hidden": False}) == {
            "visible": "1",
            "hidden": "0",
        }

    def test_none_values_are_dropped(self) -> None:
        assert flatten_ws_params({"courseid": 3, "idnumber": None}) == {"courseid": "3"}

    def test_empty_mapping_flattens_to_nothing(self) -> None:
        assert flatten_ws_params({}) == {}


def _mock_session(body: str, status: int = 200) -> MagicMock:
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=body)
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None

    session = MagicMock()
    session.request.return_value = response
    session.closed = False
    session.close = AsyncMock()
    return session


class TestMoodleClientEnvelope:
    @pytest.mark.asyncio
    async def test_successful_call_returns_the_parsed_body(self) -> None:
        session = _mock_session('{"sitename": "Sparkth Moodle Dev"}')
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            async with MoodleClient("https://moodle.example.com", "tok") as client:
                result = await client.call_dict("core_webservice_get_site_info")
        assert result == {"sitename": "Sparkth Moodle Dev"}

    @pytest.mark.asyncio
    async def test_invalid_token_raises_authentication_error(self) -> None:
        body = '{"exception": "moodle_exception", "errorcode": "invalidtoken", "message": "Invalid token"}'
        session = _mock_session(body)
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            with pytest.raises(AuthenticationError) as exc_info:
                async with MoodleClient("https://moodle.example.com", "bad") as client:
                    await client.call_dict("core_webservice_get_site_info")
        assert "Invalid token" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_other_exception_codes_raise_lms_request_error(self) -> None:
        body = '{"exception": "moodle_exception", "errorcode": "nopermissions", "message": "No permission"}'
        session = _mock_session(body)
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            with pytest.raises(LMSRequestError) as exc_info:
                async with MoodleClient("https://moodle.example.com", "tok") as client:
                    await client.call_dict("local_sparkth_create_section", {"courseid": 1})
        assert "No permission" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_a_body_without_an_exception_key_is_not_an_error(self) -> None:
        session = _mock_session('{"errorcode": "unused", "id": 7}')
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            async with MoodleClient("https://moodle.example.com", "tok") as client:
                result = await client.call_dict("local_sparkth_create_section")
        assert result == {"errorcode": "unused", "id": 7}


class TestMoodleClientTypedAccessors:
    @pytest.mark.asyncio
    async def test_call_list_returns_the_parsed_array(self) -> None:
        session = _mock_session('[{"id": 1}, {"id": 2}]')
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            async with MoodleClient("https://moodle.example.com", "tok") as client:
                result = await client.call_list("core_course_get_courses")
        assert result == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_call_dict_raises_value_error_on_an_array_body(self) -> None:
        session = _mock_session('[{"id": 1}]')
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            with pytest.raises(ValueError, match="core_webservice_get_site_info"):
                async with MoodleClient("https://moodle.example.com", "tok") as client:
                    await client.call_dict("core_webservice_get_site_info")

    @pytest.mark.asyncio
    async def test_call_list_raises_value_error_on_an_object_body(self) -> None:
        session = _mock_session('{"id": 1}')
        with patch("sparkth.lib.http.ClientSession", return_value=session):
            with pytest.raises(ValueError, match="core_course_get_courses"):
                async with MoodleClient("https://moodle.example.com", "tok") as client:
                    await client.call_list("core_course_get_courses")
