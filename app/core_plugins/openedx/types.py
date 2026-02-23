from enum import Enum
from typing import Any

from pydantic import BaseModel


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
    lms_url: str
    studio_url: str
    username: str
    password: str


class RefreshTokenPayload(BaseModel):
    lms_url: str
    studio_url: str
    refresh_token: str


class LMSAccess(BaseModel):
    access_token: str
    lms_url: str


class CourseArgs(BaseModel):
    org: str
    number: str
    run: str
    title: str
    pacing_type: str


class CreateCourseArgs(BaseModel):
    auth: AccessTokenPayload
    org: str
    number: str
    run: str
    title: str
    pacing_type: str


class ListCourseRunsArgs(BaseModel):
    auth: AccessTokenPayload
    page: int | None = None
    page_size: int | None = None


class XBlock(BaseModel):
    parent_locator: str
    category: str
    display_name: str


class XBlockPayload(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    parent_locator: str
    category: str
    display_name: str


class Component(str, Enum):
    PROBLEM = "Problem"
    HTML = "Html"


class ProblemOrHtmlArgs(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    unit_locator: str
    kind: Component | None = None
    display_name: str | None = None
    data: str | None = None
    metadata: dict[str, Any] | None = None
    mcq_boilerplate: bool | None = None


class UpdateXBlockPayload(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    locator: str
    data: str | None = None
    metadata: dict[str, Any] | None = None


class CourseTreeRequest(BaseModel):
    auth: AccessTokenPayload
    course_id: str


class BlockContentArgs(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    locator: str
