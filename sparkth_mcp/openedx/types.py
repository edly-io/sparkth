from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


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
    course: CourseArgs


class ListCourseRunsArgs(BaseModel):
    auth: AccessTokenPayload
    page: Optional[int] = None
    page_size: Optional[int] = None


class XBlock(BaseModel):
    parent_locator: str
    category: str
    display_name: str


class XBlockPayload(BaseModel):
    auth: AccessTokenPayload
    xblock: XBlock
    course_id: str


class Component(str, Enum):
    Problem = "Problem"
    Html = "Html"


class ProblemOrHtmlArgs(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    unit_locator: str
    kind: Optional[Component] = None
    display_name: Optional[str] = None
    data: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    mcq_boilerplate: Optional[bool] = None


class UpdateXBlockPayload(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    locator: str
    data: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class CourseTreeRequest(BaseModel):
    auth: AccessTokenPayload
    course_id: str


class BlockContentArgs(BaseModel):
    auth: AccessTokenPayload
    course_id: str
    locator: str
