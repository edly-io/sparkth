from pydantic import BaseModel


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str


class BaseError(Exception):
    def __init__(self, status_code: int, message: str):
        self.message = message
        self.status_code = status_code
        super().__init__(self._format_message())

    def _format_message(self):
        return f"{self.message} (status_code={self.status_code})"


class AuthenticationError(BaseError):
    pass


class JsonParseError(BaseError):
    pass


class LMSError(BaseError):
    def __init__(self, method: str, url: str, status_code: int, message: str):
        self.method = method
        self.url = url
        super().__init__(status_code, message)

    def _format_message(self):
        return f"{self.method} {self.url}: {self.message} (status_code={self.status_code})"
