from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.openedx.client import OpenEdxClient
from app.core_plugins.openedx.plugin import OpenEdxPlugin
from app.core_plugins.openedx.types import (
    AccessTokenPayload,
    Auth,
    BlockContentArgs,
    Component,
    CourseTreeRequest,
    CreateCourseArgs,
    ListCourseRunsArgs,
    LMSAccess,
    ProblemOrHtmlArgs,
    RefreshTokenPayload,
    UpdateXBlockPayload,
    XBlockPayload,
)
from app.mcp.types import AuthenticationError, LMSError

LMS_URL = "https://lms.example.com"
STUDIO_URL = "https://studio.example.com"
ACCESS_TOKEN = "test_access_token"
USERNAME = "testuser"
PASSWORD = "testpass"


@pytest.fixture
def auth_payload() -> AccessTokenPayload:
    return AccessTokenPayload(access_token=ACCESS_TOKEN, lms_url=LMS_URL, studio_url=STUDIO_URL)


@pytest.fixture
def plugin() -> OpenEdxPlugin:
    with patch("app.core_plugins.openedx.plugin.OpenEdxConfig"):
        return OpenEdxPlugin("open-edx")


@pytest.fixture
def mock_openedx_client() -> Generator[tuple[MagicMock, AsyncMock], None, None]:
    """Patch OpenEdxClient and yield (mock_cls, mock_client) for tests to configure."""
    with patch("app.core_plugins.openedx.plugin.OpenEdxClient") as mock_cls:
        client = AsyncMock(spec=OpenEdxClient)
        mock_cls.return_value.__aenter__.return_value = client
        mock_cls.return_value.__aexit__.return_value = None
        yield mock_cls, client


@pytest.mark.asyncio
class TestOpenEdxClient:
    async def test_authenticate_success(self) -> None:
        lms_url = "https://openedx.example.com"
        access_token = "valid_token"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"user": "test_user"})
        mock_response.text = AsyncMock(return_value='{"user": "test_user"}')

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.request.return_value = mock_cm

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url, access_token)
            result = await client.authenticate()

        assert result == {"user": "test_user"}

    async def test_request_jwt_no_token(self) -> None:
        lms_url = "https://openedx.example.com"
        client = OpenEdxClient(lms_url)

        with pytest.raises(AuthenticationError) as exc_info:
            await client.request_jwt("GET", lms_url, "api/user/v1/me")

        assert exc_info.value.args[0] == "Access token not set (status_code=401)"

    async def test_get_token_success(self) -> None:
        lms_url = "https://openedx.example.com"
        username = "user1"
        password = "pass1"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "new_token",
                "refresh_token": "refresh_token",
            }
        )
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url)
            token_data = await client.get_token(username, password)

        assert token_data["access_token"] == "new_token"
        assert client.access_token == "new_token"
        assert client.refresh_token == "refresh_token"

    async def test_refresh_access_token_success(self) -> None:
        lms_url = "https://openedx.example.com"
        old_refresh_token = "old_refresh"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"access_token": "refreshed_token", "refresh_token": "new_refresh"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url)
            token_data = await client.refresh_access_token(old_refresh_token)

        assert token_data["access_token"] == "refreshed_token"
        assert client.access_token == "refreshed_token"
        assert client.refresh_token == "new_refresh"


@pytest.mark.asyncio
class TestOpenEdxPluginAuthenticate:
    async def test_authenticate_success(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.get_token.return_value = {"access_token": "tok123", "refresh_token": "ref456"}
        client.get_username.return_value = USERNAME

        payload = Auth(lms_url=LMS_URL, studio_url=STUDIO_URL, username=USERNAME, password=PASSWORD)
        result = await plugin.openedx_authenticate(payload)

        mock_cls.assert_called_once_with(LMS_URL)
        client.get_token.assert_called_once_with(USERNAME, PASSWORD)
        assert result["access_token"] == "tok123"
        assert result["studio_url"] == STUDIO_URL

    async def test_authenticate_failure(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.get_token.side_effect = AuthenticationError(401, "Invalid credentials")

        payload = Auth(lms_url=LMS_URL, studio_url=STUDIO_URL, username=USERNAME, password="wrong")
        result = await plugin.openedx_authenticate(payload)

        assert "error" in result
        assert result["error"]["status_code"] == 401


@pytest.mark.asyncio
class TestOpenEdxPluginRefreshToken:
    async def test_refresh_success(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.refresh_access_token.return_value = {"access_token": "new_tok", "refresh_token": "new_ref"}

        payload = RefreshTokenPayload(lms_url=LMS_URL, studio_url=STUDIO_URL, refresh_token="old_ref")
        result = await plugin.openedx_refresh_access_token(payload)

        client.refresh_access_token.assert_called_once_with("old_ref")
        assert result["response"]["access_token"] == "new_tok"
        assert result["response"]["studio_url"] == STUDIO_URL

    async def test_refresh_failure(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.refresh_access_token.side_effect = AuthenticationError(401, "Invalid refresh token")

        payload = RefreshTokenPayload(lms_url=LMS_URL, studio_url=STUDIO_URL, refresh_token="bad_ref")
        result = await plugin.openedx_refresh_access_token(payload)

        assert "error" in result
        assert result["error"]["status_code"] == 401


@pytest.mark.asyncio
class TestOpenEdxPluginGetUserInfo:
    async def test_get_user_info_success(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.authenticate.return_value = {"username": "admin"}

        payload = LMSAccess(access_token=ACCESS_TOKEN, lms_url=LMS_URL)
        result = await plugin.openedx_get_user_info(payload)

        mock_cls.assert_called_once_with(LMS_URL, ACCESS_TOKEN)
        assert result["response"] == {"username": "admin"}

    async def test_get_user_info_failure(
        self, plugin: OpenEdxPlugin, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.authenticate.side_effect = AuthenticationError(401, "Unauthorized")

        payload = LMSAccess(access_token="bad_token", lms_url=LMS_URL)
        result = await plugin.openedx_get_user_info(payload)

        assert "error" in result
        assert result["error"]["status_code"] == 401


@pytest.mark.asyncio
class TestOpenEdxPluginCreateCourseRun:
    async def test_create_course_run_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.post.return_value = {"id": "course-v1:TestOrg+101+2024"}

        payload = CreateCourseArgs(
            auth=auth_payload, org="TestOrg", number="101", run="2024", title="Test Course", pacing_type="self_paced"
        )
        result = await plugin.openedx_create_course_run(payload)

        mock_cls.assert_called_once_with(LMS_URL, ACCESS_TOKEN)
        client.post.assert_called_once_with(
            STUDIO_URL,
            "api/v1/course_runs/",
            {"org": "TestOrg", "number": "101", "run": "2024", "title": "Test Course", "pacing_type": "self_paced"},
        )
        assert result["response"]["id"] == "course-v1:TestOrg+101+2024"

    async def test_create_course_run_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(403, "Forbidden")

        payload = CreateCourseArgs(
            auth=auth_payload, org="TestOrg", number="101", run="2024", title="Test Course", pacing_type="self_paced"
        )
        result = await plugin.openedx_create_course_run(payload)

        assert result["error"]["status_code"] == 403


@pytest.mark.asyncio
class TestOpenEdxPluginListCourseRuns:
    async def test_list_course_runs_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.get.return_value = {"results": [{"id": "course-v1:Org+101+2024"}]}

        payload = ListCourseRunsArgs(auth=auth_payload, page=1, page_size=10)
        result = await plugin.openedx_list_course_runs(payload)

        assert "courses" in result

    async def test_list_course_runs_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = AuthenticationError(401, "Unauthorized")

        payload = ListCourseRunsArgs(auth=auth_payload)
        result = await plugin.openedx_list_course_runs(payload)

        assert result["error"]["status_code"] == 401


@pytest.mark.asyncio
class TestOpenEdxPluginCreateXBlock:
    async def test_create_xblock_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new"}

        payload = XBlockPayload(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            parent_locator="block-v1:parent",
            category="chapter",
            display_name="Week 1",
        )
        result = await plugin.openedx_create_xblock(payload)

        mock_cls.assert_called_once_with(LMS_URL, ACCESS_TOKEN)
        assert result["response"] == {"locator": "block-v1:new"}

    async def test_create_xblock_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(403, "Forbidden")

        payload = XBlockPayload(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            parent_locator="block-v1:parent",
            category="chapter",
            display_name="Week 1",
        )
        result = await plugin.openedx_create_xblock(payload)

        assert result["error"]["status_code"] == 403


@pytest.mark.asyncio
class TestOpenEdxPluginUpdateXBlock:
    async def test_update_xblock_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.patch.return_value = {"status": "ok"}

        payload = UpdateXBlockPayload(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            locator="block-v1:loc",
            data="<p>Updated</p>",
        )
        result = await plugin.openedx_update_xblock(payload)

        assert result["response"] == {"status": "ok"}

    async def test_update_xblock_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.patch.side_effect = AuthenticationError(500, "Server error")

        payload = UpdateXBlockPayload(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            locator="block-v1:loc",
            data="<p>Updated</p>",
        )
        result = await plugin.openedx_update_xblock(payload)

        assert result["error"]["status_code"] == 500


@pytest.mark.asyncio
class TestOpenEdxPluginGetCourseTree:
    async def test_get_course_tree_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.get.return_value = {"blocks": {"root": {}}}

        payload = CourseTreeRequest(auth=auth_payload, course_id="course-v1:Org+101+2024")
        result = await plugin.openedx_get_course_tree_raw(payload)

        mock_cls.assert_called_once_with(LMS_URL, ACCESS_TOKEN)
        assert result["response"] == {"blocks": {"root": {}}}

    async def test_get_course_tree_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = LMSError("GET", "/api/courses/v1/blocks/", 404, "Not found")

        payload = CourseTreeRequest(auth=auth_payload, course_id="course-v1:Org+101+2024")
        result = await plugin.openedx_get_course_tree_raw(payload)

        assert result["error"]["status_code"] == 404


@pytest.mark.asyncio
class TestOpenEdxPluginGetBlockContentstore:
    async def test_get_block_contentstore_success(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        mock_cls, client = mock_openedx_client
        client.get.return_value = {"data": "<p>Hello</p>"}

        payload = BlockContentArgs(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            locator="block-v1:Org+101+2024+type@html+block@abc",
        )
        result = await plugin.openedx_get_block_contentstore(payload)

        mock_cls.assert_called_once_with(LMS_URL, ACCESS_TOKEN)
        assert result["response"] == {"data": "<p>Hello</p>"}

    async def test_get_block_contentstore_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.get.side_effect = LMSError("GET", "/api/contentstore/", 404, "Not found")

        payload = BlockContentArgs(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            locator="block-v1:bad",
        )
        result = await plugin.openedx_get_block_contentstore(payload)

        assert result["error"]["status_code"] == 404


@pytest.mark.asyncio
class TestOpenEdxPluginCreateProblemOrHtml:
    async def test_create_problem_with_data(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new_problem"}
        client.patch.return_value = {"status": "updated"}

        payload = ProblemOrHtmlArgs(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            unit_locator="block-v1:unit",
            data="<problem><p>Q?</p></problem>",
        )
        result = await plugin.openedx_create_problem_or_html(payload)

        assert "response" in result
        assert result["response"]["locator"] == "block-v1:new_problem"

    async def test_create_html_no_data(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.return_value = {"locator": "block-v1:new_html"}

        payload = ProblemOrHtmlArgs(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            unit_locator="block-v1:unit",
            kind=Component.HTML,
        )
        result = await plugin.openedx_create_problem_or_html(payload)

        assert result["response"]["locator"] == "block-v1:new_html"
        assert result["response"]["result"]["detail"] == "Component created; no content/metadata to update"

    async def test_create_problem_auth_failure(
        self, plugin: OpenEdxPlugin, auth_payload: AccessTokenPayload, mock_openedx_client: tuple[MagicMock, AsyncMock]
    ) -> None:
        _, client = mock_openedx_client
        client.post.side_effect = AuthenticationError(401, "Unauthorized")

        payload = ProblemOrHtmlArgs(
            auth=auth_payload,
            course_id="course-v1:Org+101+2024",
            unit_locator="block-v1:unit",
        )
        result = await plugin.openedx_create_problem_or_html(payload)

        assert result["error"]["status_code"] == 401
