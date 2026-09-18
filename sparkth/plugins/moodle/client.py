from typing import Any

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.lib.http import BaseHttpClient
from sparkth.plugins.moodle.constants import MOODLE_AUTH_ERROR_CODES, MOODLE_WS_ENDPOINT


def flatten_ws_params(value: Any, prefix: str = "") -> dict[str, str]:
    """Flatten nested parameters into Moodle's bracketed form-encoding.

    Moodle's REST server does not accept JSON. A nested structure is expressed as
    ``courses[0][fullname]=Intro``. ``None`` values are dropped rather than sent
    empty, because Moodle rejects an empty string for a typed parameter.
    """
    if isinstance(value, dict):
        flattened: dict[str, str] = {}
        for key, item in value.items():
            child = f"{prefix}[{key}]" if prefix else str(key)
            flattened.update(flatten_ws_params(item, child))
        return flattened

    if isinstance(value, list):
        indexed: dict[str, str] = {}
        for index, item in enumerate(value):
            indexed.update(flatten_ws_params(item, f"{prefix}[{index}]"))
        return indexed

    if value is None:
        return {}

    if isinstance(value, bool):
        return {prefix: "1" if value else "0"}

    return {prefix: str(value)}


def _raise_on_ws_exception(wsfunction: str, body: Any) -> None:
    """Raise when a Moodle web service response carries an exception envelope.

    Moodle answers a failed call with HTTP 200 and a body describing the failure, so
    the status line carries no information and the body must be inspected. The
    reported status is chosen here rather than echoed: 401 when the token itself is
    rejected, 400 otherwise, since the remaining codes are caller-side faults.
    """
    if not isinstance(body, dict) or "exception" not in body:
        return

    errorcode = str(body.get("errorcode", ""))
    message = str(body.get("message") or errorcode or "Moodle web service call failed")

    if errorcode in MOODLE_AUTH_ERROR_CODES:
        raise AuthenticationError(401, message)

    raise LMSRequestError(Method.POST, wsfunction, 400, message)


class MoodleClient(BaseHttpClient):
    """HTTP client for Moodle's REST web services API.

    Every call posts form-encoded parameters to a single endpoint and selects the
    operation with ``wsfunction``, rather than addressing REST resources by path.
    """

    def __init__(self, api_url: str, api_token: str) -> None:
        super().__init__(api_url)
        self.api_token = api_token

    @property
    def token(self) -> str | None:
        return self.api_token or None

    async def call(self, wsfunction: str, params: dict[str, Any] | None = None) -> Any:
        """Invoke a web service function and return its parsed response body."""
        body = {
            "wstoken": self.api_token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }
        body.update(flatten_ws_params(params or {}))

        result = await self._request(Method.POST, MOODLE_WS_ENDPOINT, data=body)
        _raise_on_ws_exception(wsfunction, result)
        return result
