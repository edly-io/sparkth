from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenEdxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    lms_url: str
    studio_url: str
    lms_username: str
    lms_password: str


@lru_cache
def get_openedx_settings() -> OpenEdxSettings:
    return OpenEdxSettings()


class OpenEdxSettings(BaseSettings):    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    lms_url: str | None = None
    studio_url: str | None = None
    username: str
    password: str

openedx_settings = OpenEdxSettings()

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    scope: str | None = None


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
    page: int | None | None = None
    page_size: int | None | None = None


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
    kind: Component | None = None
    display_name: str | None = None
    data: str | None = None
    metadata: dict[str, Any] | None = None
    mcq_boilerplate: bool | None = None


class UpdateXBlockPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str
    course_id: str
    locator: str
    data: str | None = None
    metadata: dict[str, Any] | None = None


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
    