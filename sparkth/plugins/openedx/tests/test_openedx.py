from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth.plugins.openedx.tools as openedx_tools
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.lib.testing import FakeRedis, seed_plugin_settings, tool_input_property_names
from sparkth.plugins.openedx.client import OpenEdxClient
from sparkth.plugins.openedx.constants import OPENEDX_PLUGIN_NAME
from sparkth.plugins.openedx.enums import Component
from sparkth.plugins.openedx.plugin import OpenEdxPlugin
from sparkth.plugins.openedx.schemas import (
    BlockContentArgs,
    CourseTreeRequest,
    CreateCourseArgs,
    ListCourseRunsArgs,
    ProblemOrHtmlArgs,
    UpdateXBlockPayload,
    XBlockPayload,
)
from sparkth.plugins.openedx.tests.conftest import OPENEDX_CONFIG, http_response, http_session

LMS = str(OPENEDX_CONFIG.lms_url).rstrip("/")
STUDIO = str(OPENEDX_CONFIG.studio_url).rstrip("/")


@pytest.fixture
def mock_openedx_client() -> Generator[tuple[MagicMock, AsyncMock], None, None]:
    """Patch OpenEdxClient and yield (mock_cls, mock_client) for tests to configure."""
    with patch("sparkth.plugins.openedx.tools.OpenEdxClient") as mock_cls:
        client = AsyncMock(spec=OpenEdxClient)
        client.studio_url = STUDIO
        client.base_url = LMS
        mock_cls.return_value.__aenter__.return_value = client
        mock_cls.return_value.__aexit__.return_value = None
        yield mock_cls, client


async def test_a_tool_calls_open_edx_with_the_callers_stored_settings(
    session: AsyncSession, fake_redis: FakeRedis
) -> None:
    stored = {
        "lms_url": "https://stored-lms.example.com",
        "studio_url": "https://stored-studio.example.com",
        "lms_username": "stored-user",
        "lms_password": "stored-pass",
    }
    await seed_plugin_settings(session, OPENEDX_PLUGIN_NAME, stored)
    bind_current_user_id(1)
    http = http_session('{"access_token": "granted"}', http_response(200, '{"blocks": {}}'))

    with patch("sparkth.lib.http.ClientSession", return_value=http):
        result = await openedx_tools.openedx_get_course_tree_raw(CourseTreeRequest(course_id="course-v1:Org+101+2024"))

    assert result == {"response": {"blocks": {}}}
    assert http.post.call_args.args[0] == "https://stored-lms.example.com/oauth2/access_token"
    assert http.post.call_args.kwargs["data"]["username"] == "stored-user"
    assert http.post.call_args.kwargs["data"]["password"] == "stored-pass"
    assert http.request.call_args.args[1] == "https://stored-lms.example.com/api/courses/v1/blocks/"
    assert http.request.call_args.kwargs["headers"]["Authorization"] == "Jwt granted"


def test_no_open_edx_tool_takes_a_credential() -> None:
    plugin = OpenEdxPlugin()
    names = tool_input_property_names(plugin)

    assert "course_id" in names
    assert not names & {"auth", "lms_url", "studio_url", "username", "password", "access_token", "refresh_token"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxCheckSettings:
    async def test_returns_the_signed_in_account(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.authenticate.return_value = {"username": "admin"}

        result = await openedx_tools.openedx_check_settings()

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        assert result["response"] == {"username": "admin"}

    async def test_rejected_settings_become_an_error_dict(
        self, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.authenticate.side_effect = AuthenticationError(401, "Unauthorized")

        result = await openedx_tools.openedx_check_settings()

        assert "error" in result
        assert result["error"]["status_code"] == 401


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginCreateCourseRun:
    async def test_create_course_run_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:TestOrg+101+2024"}

        payload = CreateCourseArgs(
            org="TestOrg", number="101", run="2024", title="Test Course", pacing_type="self_paced"
        )
        result = await openedx_tools.openedx_create_course_run(payload)

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        client.post.assert_called_once_with(
            STUDIO,
            "api/v1/course_runs/",
            {"org": "TestOrg", "number": "101", "run": "2024", "title": "Test Course", "pacing_type": "self_paced"},
        )
        assert result["response"]["id"] == "course-v1:TestOrg+101+2024"

    async def test_create_course_run_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(403, "Forbidden")

        payload = CreateCourseArgs(
            org="TestOrg", number="101", run="2024", title="Test Course", pacing_type="self_paced"
        )
        result = await openedx_tools.openedx_create_course_run(payload)

        assert result["error"]["status_code"] == 403


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginListCourseRuns:
    async def test_list_course_runs_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.get.return_value = {"results": [{"id": "course-v1:Org+101+2024"}]}

        result = await openedx_tools.openedx_list_course_runs(ListCourseRunsArgs(page=1, page_size=10))

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        client.get.assert_called_once_with(STUDIO, "api/v1/course_runs/?page=1&page_size=10")
        assert result["courses"] == {"results": [{"id": "course-v1:Org+101+2024"}]}

    async def test_list_course_runs_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = AuthenticationError(401, "Unauthorized")

        result = await openedx_tools.openedx_list_course_runs(ListCourseRunsArgs())

        assert result["error"]["status_code"] == 401


def _xblock_payload() -> XBlockPayload:
    return XBlockPayload(
        course_id="course-v1:Org+101+2024", parent_locator="block-v1:parent", category="chapter", display_name="Week 1"
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginCreateXBlock:
    async def test_create_xblock_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new"}

        result = await openedx_tools.openedx_create_xblock(_xblock_payload())

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        assert client.post.call_args.args[0] == STUDIO
        assert result["response"] == {"locator": "block-v1:new"}

    async def test_create_xblock_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(403, "Forbidden")

        result = await openedx_tools.openedx_create_xblock(_xblock_payload())

        assert result["error"]["status_code"] == 403


def _update_payload() -> UpdateXBlockPayload:
    return UpdateXBlockPayload(course_id="course-v1:Org+101+2024", locator="block-v1:loc", data="<p>Updated</p>")


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginUpdateXBlock:
    async def test_update_xblock_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.patch.return_value = {"status": "ok"}

        result = await openedx_tools.openedx_update_xblock(_update_payload())

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        assert client.patch.call_args.args[0] == STUDIO
        assert result["response"] == {"status": "ok"}

    async def test_update_xblock_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.patch.side_effect = AuthenticationError(500, "Server error")

        result = await openedx_tools.openedx_update_xblock(_update_payload())

        assert result["error"]["status_code"] == 500


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginGetCourseTree:
    async def test_get_course_tree_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.get.return_value = {"blocks": {"root": {}}}

        result = await openedx_tools.openedx_get_course_tree_raw(CourseTreeRequest(course_id="course-v1:Org+101+2024"))

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        assert client.get.call_args.args[0] == LMS
        assert result["response"] == {"blocks": {"root": {}}}

    async def test_get_course_tree_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = LMSRequestError(Method.GET, "/api/courses/v1/blocks/", 404, "Not found")

        result = await openedx_tools.openedx_get_course_tree_raw(CourseTreeRequest(course_id="course-v1:Org+101+2024"))

        assert result["error"]["status_code"] == 404


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginGetBlockContentstore:
    async def test_get_block_contentstore_success(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        mock_cls, client = mock_openedx_client
        client.get.return_value = {"data": "<p>Hello</p>"}

        payload = BlockContentArgs(
            course_id="course-v1:Org+101+2024", locator="block-v1:Org+101+2024+type@html+block@abc"
        )
        result = await openedx_tools.openedx_get_block_contentstore(payload)

        mock_cls.assert_called_once_with(OPENEDX_CONFIG, 1)
        assert client.get.call_args.args[0] == STUDIO
        assert result["response"] == {"data": "<p>Hello</p>"}

    async def test_get_block_contentstore_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = LMSRequestError(Method.GET, "/api/contentstore/", 404, "Not found")

        payload = BlockContentArgs(course_id="course-v1:Org+101+2024", locator="block-v1:bad")
        result = await openedx_tools.openedx_get_block_contentstore(payload)

        assert result["error"]["status_code"] == 404


@pytest.mark.asyncio
@pytest.mark.usefixtures("stored_config")
class TestOpenEdxPluginCreateProblemOrHtml:
    async def test_create_problem_with_data(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new_problem"}
        client.patch.return_value = {"status": "updated"}

        payload = ProblemOrHtmlArgs(
            course_id="course-v1:Org+101+2024", unit_locator="block-v1:unit", data="<problem><p>Q?</p></problem>"
        )
        result = await openedx_tools.openedx_create_problem_or_html(payload)

        assert client.post.call_args.args[0] == STUDIO
        assert client.patch.call_args.args[0] == STUDIO
        assert result["response"]["locator"] == "block-v1:new_problem"

    async def test_create_html_no_data(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new_html"}

        payload = ProblemOrHtmlArgs(
            course_id="course-v1:Org+101+2024", unit_locator="block-v1:unit", kind=Component.HTML
        )
        result = await openedx_tools.openedx_create_problem_or_html(payload)

        assert result["response"]["locator"] == "block-v1:new_html"
        assert result["response"]["result"]["detail"] == "Component created; no content/metadata to update"

    async def test_create_problem_auth_failure(self, mock_openedx_client: tuple[MagicMock, AsyncMock]) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(401, "Unauthorized")

        payload = ProblemOrHtmlArgs(course_id="course-v1:Org+101+2024", unit_locator="block-v1:unit")
        result = await openedx_tools.openedx_create_problem_or_html(payload)

        assert result["error"]["status_code"] == 401
