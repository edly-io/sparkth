from pydantic import BaseModel


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str
