"""Legacy HTTP-carrying exceptions, kept for existing LMS-client callers.

These classes predate the exception→HTTP mapping standard (CLAUDE.md,
"Domain exceptions → HTTP responses"): they carry ``status_code`` on the exception
itself. New code must NOT follow this pattern — raise an HTTP-agnostic domain exception
and map it to a status via ``register_exception_handler`` (``sparkth.lib.exceptions.handlers``)
instead.
"""

from sparkth.lib.enums import Method


class HttpError(Exception):
    def __init__(self, status_code: int, message: str):
        self.message = message
        self.status_code = status_code
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return f"{self.message} (status_code={self.status_code})"


class AuthenticationError(HttpError):
    pass


class LMSRequestError(HttpError):
    def __init__(self, method: Method, url: str, status_code: int, message: str):
        self.method = method
        self.url = url
        super().__init__(status_code, message)

    def _format_message(self) -> str:
        return f"{self.method} {self.url}: {self.message} (status_code={self.status_code})"
