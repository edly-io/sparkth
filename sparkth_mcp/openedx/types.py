from typing import Optional
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
