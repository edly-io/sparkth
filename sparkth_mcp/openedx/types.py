from typing import Optional
from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None


class OpenEdxAccessTokenPayload(BaseModel):
    access_token: str
    lms_url: str
    studio_url: str


class OpenEdxAuth(BaseModel):
    lms_url: str
    studio_url: str
    username: str
    password: str
