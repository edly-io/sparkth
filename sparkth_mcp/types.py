from pydantic import BaseModel


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str


class AuthenticationError(Exception):
    def __init__(self, status_code, message):
        self.message = message
        self.status_code = status_code
        super().__init__(f"{message} (status_code={status_code})")


class LMSError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"{message} (status_code={status_code})")
