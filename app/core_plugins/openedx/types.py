from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenEdxSettings(BaseSettings):    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    lms_url: Optional[str] = None
    studio_url: Optional[str] = None
    lms_username: str
    lms_password: str

openedx_settings = OpenEdxSettings()

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None


class AccessTokenPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str


class Auth(BaseModel):
    lms_url: str | None
    studio_url: str | None
    username: str | None
    password: str | None


class RefreshTokenPayload(BaseModel):
    lms_url: str | None
    studio_url: str | None
    refresh_token: str


class LMSAccess(BaseModel):
    access_token: str
    lms_url: str | None


class CourseArgs(BaseModel):
    org: str
    number: str
    run: str
    title: str
    pacing_type: str


class CreateCourseArgs(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    org: str
    number: str
    run: str
    title: str
    pacing_type: str


class ListCourseRunsArgs(BaseModel):
    # auth: AccessTokenPayload
    access_token: str
    lms_url: str
    studio_url: str
    page: Optional[int] = None
    page_size: Optional[int] = None


class XBlock(BaseModel):
    parent_locator: str
    category: str
    display_name: str


class XBlockPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str
    parent_locator: str
    category: str
    display_name: str


class Component(str, Enum):
    PROBLEM = "Problem"
    HTML = "Html"


class ProblemOrHtmlArgs(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str
    unit_locator: str
    kind: Optional[Component] = None
    display_name: Optional[str] = None
    data: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    mcq_boilerplate: Optional[bool] = None


class UpdateXBlockPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str
    locator: str
    data: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CourseTreeRequest(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str


class BlockContentArgs(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str
    locator: str
    