from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    name: str
    username: str
    password: str


class User(UserBase):
    id: int
    name: str
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserWithRoles(User):
    """User response that includes role information."""

    roles: list[str] = []


class RoleSchema(BaseModel):
    role: str


class AssignRoleRequest(BaseModel):
    role: str


class AdminUserList(BaseModel):
    """Paginated user list for admin endpoints."""

    users: list[UserWithRoles]
    total: int
    page: int
    page_size: int


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime


class TokenData(BaseModel):
    username: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class GoogleAuthUrl(BaseModel):
    url: str
