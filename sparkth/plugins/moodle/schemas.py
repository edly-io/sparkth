from pydantic import BaseModel, Field


class Auth(BaseModel):
    api_url: str = Field(..., description="Moodle site URL")
    api_token: str = Field(..., description="Moodle web service token")


class CoursePayload(BaseModel):
    auth: Auth
    fullname: str = Field(..., description="Course full name")
    shortname: str = Field(..., description="Course short name, unique on the site")
    categoryid: int = Field(1, description="Category to create the course in")
    summary: str = Field("", description="Course summary HTML")
    lang: str = Field("", description="Course language code, empty for the site default")
